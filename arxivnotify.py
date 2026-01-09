#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function
import urllib.request
import urllib.parse
from xml.etree import ElementTree
import requests
import datetime
import dateutil.parser
import time
import configparse
from ollama import Client
from weasyprint import HTML, CSS
import io

def build_query(queries, page, num_elements):
    query = "http://export.arxiv.org/api/query?search_query="
    search_element = ""
    if len(queries) == 0:
        search_element = '""'
    for i in range(len(queries)):
        search_element = search_element + '"{}"'.format(urllib.parse.quote(str(queries[i])))
        if i + 1 != len(queries):
            search_element = search_element + "+OR+"
    suffix = "&sortBy=lastUpdatedDate&sortOrder=descending&start={}&max_results={}".format(str(page), str(num_elements))
    return query + search_element + suffix

def fetch_queries(queries, query_time):
    do_continue = True
    current_page = 0
    pager_interval = 30
    fetched_data = []

    while do_continue:
        q_raw = build_query(queries, current_page * pager_interval, pager_interval)
        q_clean = urllib.parse.quote(q_raw, safe=':/?&=+')
        req = urllib.request.Request(q_clean, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            query_page = urllib.request.urlopen(req)
            query_data = query_page.read().decode("utf8")
            query_page.close()
        except urllib.error.HTTPError as e:
            print(f"Errore HTTP {e.code}: {e.reason}")
            break

        page_root = ElementTree.fromstring(query_data)
        articles = page_root.findall("{http://www.w3.org/2005/Atom}entry")

        if not articles:
            break

        update_text = page_root.findtext("{http://www.w3.org/2005/Atom}updated")
        oldest_query_time = dateutil.parser.parse(update_text) - datetime.timedelta(days=int(query_time))

        time.sleep(3)

        for article in articles:
            link = article.findtext("{http://www.w3.org/2005/Atom}id")
            title = article.findtext("{http://www.w3.org/2005/Atom}title").replace('\n', ' ')
            abstract = article.findtext("{http://www.w3.org/2005/Atom}summary")
            date = article.findtext("{http://www.w3.org/2005/Atom}updated")
            authors = ", ".join([name.text for name in article.iter("{http://www.w3.org/2005/Atom}name")])
            datetime_obj = dateutil.parser.parse(date)

            categories = article.findall("{http://www.w3.org/2005/Atom}category")
            tags_list = [cat.get("term") for cat in categories]

            if datetime_obj < oldest_query_time:
                do_continue = False
                break

            fetched_data.append((title, link, abstract, datetime_obj, authors, tags_list))
        current_page += 1

    return fetched_data

def _send_telegram_pdf(mail_subject, html_output):
    dark_css = """
        @page { background-color: #1a1a1a; margin: 1cm; }
        body { background-color: #1a1a1a; color: #e0e0e0; font-family: sans-serif; line-height: 1.5; }
        h1, h2, h3 { color: #ffffff; border-bottom: 1px solid #444; padding-bottom: 10px; }
        a { color: #88ccff; text-decoration: none; }
        li { margin-bottom: 15px; padding: 10px; background-color: #262626; border-radius: 5px; list-style-type: none; }
        b { color: #ffcc80; }
        .tag-container { margin: 5px 0; }
        .tag { background-color: #334455; color: #88ccff; padding: 2px 8px; border-radius: 8px; font-size: 0.75em; font-weight: bold; display: inline-block; margin-right: 5px; border: 1px solid #445566; }
        .kw-container { margin: 5px 0; font-size: 0.8em; color: #ffcc80; }
        .kw-label { font-weight: bold; color: #aaa; text-transform: uppercase; font-size: 0.7em; margin-right: 5px; }
        .authors { color: #bbbbbb; font-size: 0.85em; }
        .date { color: #888888; font-size: 0.8em; }
        .abstract { font-size: 0.9em; margin-top: 10px; text-align: justify; color: #ccc; }
    """
    try:
        pdf_file = io.BytesIO()
        HTML(string=html_output).write_pdf(pdf_file, stylesheets=[CSS(string=dark_css)])
        pdf_file.seek(0)
        for chat_id in CFG["TELEGRAM_CHAT_IDS"]:
            url = f"https://api.telegram.org/bot{CFG['TELEGRAM_BOT_TOKEN']}/sendDocument"
            files = {"document": (f"{mail_subject.replace(' ', '_')}.pdf", pdf_file, "application/pdf")}
            requests.post(url, data={"chat_id": chat_id, "caption": mail_subject}, files=files)
            pdf_file.seek(0)
    except Exception as e:
        print(f"Failed to send PDF: {e}")

if __name__ == "__main__":
    CFG = configparse.parse("arxivnotify.cfg")
    for key in ["KEYWORD", "TAG", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS", "OLLAMA_HOST", "OLLAMA_MODEL"]:
        if key in ["KEYWORD", "TAG", "TELEGRAM_CHAT_IDS"] and not isinstance(CFG[key], list):
            CFG[key] = [CFG[key]]

    unique_papers = {}
    all_found_tags = set()

    for kw in CFG["KEYWORD"]:
        print(f"Fetching: {kw}")
        results = fetch_queries([kw], CFG["HISTORY_DAYS"])
        for paper in results:
            link = paper[1]
            tags = paper[5]
            all_found_tags.update(tags)
            if link not in unique_papers:
                if any(t in CFG["TAG"] for t in tags):
                    unique_papers[link] = {"data": paper, "matched_keywords": {kw}}
            else:
                unique_papers[link]["matched_keywords"].add(kw)

    print("\n--- TAGS FOUND ---\n" + ", ".join(sorted(list(all_found_tags))) + "\n")

    html_sections = ""
    fully_displayed_links = set()
    total_articles = 0

    for filter_tag in CFG["TAG"]:
        tag_articles = [v for v in unique_papers.values() if filter_tag in v["data"][5]]
        if not tag_articles: continue

        html_sections += f"<h3>Tag: {filter_tag}</h3><ul>"
        for entry in tag_articles:
            p = entry["data"]
            kws = entry["matched_keywords"]
            title, link, abstract, date_obj, authors, tags = p
            html_sections += "<li>"
            if link not in fully_displayed_links:
                total_articles += 1
                html_sections += f'<b><a href="{link}">{title}</a></b><br>'
                html_sections += '<div class="tag-container">' + "".join([f'<span class="tag">{t}</span>' for t in tags]) + '</div>'
                html_sections += f'<i class="authors">{authors}</i><br><span class="date">{date_obj.strftime("%Y-%m-%d")}</span>'
                html_sections += f'<p class="abstract">{abstract}</p>'
                html_sections += f'<div class="kw-container"><span class="kw-label">Matched Keywords:</span> {", ".join(kws)}</div>'
                fully_displayed_links.add(link)
            else:
                html_sections += f'<b>[Vedi sopra]</b> <a href="{link}">{title}</a>'
            html_sections += "</li>"
        html_sections += "</ul>"

    if total_articles > 0:
        mail_subject = f"ArXiv Report - {datetime.date.today().strftime('%B %d, %Y')} - {total_articles} Articles"
        html_sections = f"""<h2> Your Daily ArXiV - {datetime.date.today().strftime("%B %d, %Y")}</h2>

    {html_sections}
    """
        _send_telegram_pdf(mail_subject, f"<html><body>{html_sections}</body></html>")
    else:
        print("Nessun articolo trovato.")
