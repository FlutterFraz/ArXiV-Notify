#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ArXiV Notify script
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Copyright David Chan, 2018


from __future__ import unicode_literals, print_function


# HTML Request sending and parsing
#import urllib
import urllib.request
import urllib.parse
from xml.etree import ElementTree
import requests

# Import time utilities for handling the time values
import datetime
import dateutil.parser
import time

# Import the config parser
import configparse

from ollama import Client
import requests
from weasyprint import HTML, CSS
import io

## Build an ArXiV API Query which will query for the key
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


## Fetch the articles which are up to date
# that is, have been updated in the last day
def fetch_queries(queries, query_time):
    do_continue = True
    current_page = 0  # Which current page we are on
    pager_interval = 30  # How many articles to fetch at once
    fetched_data = []  # Each of the articles, their abstracts, and links

    while do_continue:
        # 1. Genera l'URL
        q_raw = build_query(queries, current_page * pager_interval, pager_interval)
        # 2. Encoding dell'URL (fondamentale per gli spazi nella keyword)
        q_clean = urllib.parse.quote(q_raw, safe=':/?&=+')
        # 3. Richiesta con User-Agent per evitare blocchi
        req = urllib.request.Request(q_clean, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            query_page = urllib.request.urlopen(req)
            query_bytes = query_page.read()
            query_data = query_bytes.decode("utf8")
            query_page.close()
        except urllib.error.HTTPError as e:
            print(f"Errore HTTP {e.code}: {e.reason}")
            print(f"URL incriminato: {q_clean}")
            break

        page_root = ElementTree.fromstring(query_data)
        articles = page_root.findall("{http://www.w3.org/2005/Atom}entry")
        oldest_query_time = dateutil.parser.parse(
            page_root.findtext("{http://www.w3.org/2005/Atom}updated")
        ) - datetime.timedelta(days=int(query_time))

        # Break the loop if no articles found!
        if not articles:
            do_continue = False
            print('no articles found')
            break

        # We put this sleep in to coform to the ArXiV bot standards
        time.sleep(3)

        # Build up the dataset of articles that we fetched
        for article in articles:
            link = article.findtext("{http://www.w3.org/2005/Atom}id")
            title = article.findtext("{http://www.w3.org/2005/Atom}title")
            abstract = article.findtext("{http://www.w3.org/2005/Atom}summary")
            date = article.findtext("{http://www.w3.org/2005/Atom}updated")
            authors = ", ".join([name.text for name in article.iter("{http://www.w3.org/2005/Atom}name")])
            datetime_obj = dateutil.parser.parse(date)

            categories = article.findall("{http://www.w3.org/2005/Atom}category")
            tags = [cat.get("term") for cat in categories]
            tags_str = ", ".join(tags)
            # If the published articles is too old - we're done looking.
            if datetime_obj < oldest_query_time:
                do_continue = False
                print('article too old')
                fetched_data.append((title, link, abstract, datetime_obj, authors, tags_str))
                break

            # Otherwise add the article
            fetched_data.append((title, link, abstract, datetime_obj, authors, tags_str))
        current_page += 1

    return fetched_data


def _summarize(queries, topics):
    """Summarize the queries using a remote Ollama instance"""
    # Get the abstracts and titles
    abstracts = [q[2] for q in queries]
    titles = [q[0] for q in queries]
    abstracts_and_titles = "\n\n".join([f"{t}: {a}" for t, a in zip(titles, abstracts)])

    prompt = f"""The following are the titles and abstracts of the papers that you have been reading in the last time period.
    Briefly summarize them (while retaining the necessary detail) as if you were giving a report on the following topics: {topics}.{abstracts_and_titles}"""
    # Initialize the client with the remote machine's IP
    # Default port is 11434
    client = Client(host=CFG["OLLAMA_HOST"])
    response = client.chat(model='qwen3:8b', messages=[{'role': 'user','content': prompt}])
    return response['message']['content']


def _send_telegram_pdf(mail_subject, html_output):

    dark_css = """
        @page {
            background-color: #1a1a1a; /* Colore margini foglio */
            margin: 1cm;
        }
        body {
            background-color: #1a1a1a;
            color: #e0e0e0; /* Testo grigio chiaro */
            font-family: sans-serif;
            line-height: 1.5;
            margin: 0;
            padding: 0;
        }
        h1, h2, h3 {
            color: #ffffff; /* Titoli bianchi */
            border-bottom: 1px solid #444;
            padding-bottom: 10px;
        }
        a {
            color: #88ccff; /* Link azzurro chiaro per contrasto */
            text-decoration: none;
        }
        li {
            margin-bottom: 15px;
            padding: 10px;
            background-color: #262626; /* Sfondo leggermente più chiaro per ogni paper */
            border-radius: 5px;
        }
        b {
            color: #ffcc80; /* Evidenzia i titoli dei paper in arancio pastello */
        }

        h3 {
                color: #ffcc80; /* Colore keyword (arancio/giallo) */
                border-bottom: 2px solid #444;
                margin-top: 30px;
            }
            .tag-container {
                margin: 5px 0;
            }
            .tag {
                background-color: #334455; /* Blu scuro/grigio per il badge */
                color: #88ccff;            /* Testo azzurro */
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 0.75em;
                font-weight: bold;
                display: inline-block;
                margin-right: 5px;
                border: 1px solid #445566;
            }
            .authors {
                color: #bbbbbb;
                font-size: 0.85em;
            }
            .date {
                color: #888888;
                font-size: 0.8em;
            }

    """

    try:
        # 1. Generate PDF in memory (no need to save a local file)
        pdf_file = io.BytesIO()
        HTML(string=html_output).write_pdf(pdf_file,
                    stylesheets=[CSS(string=dark_css)])

        pdf_file.seek(0) # Reset pointer to the start of the file

        # 2. Send to each recipient
        for chat_id in CFG["TELEGRAM_CHAT_IDS"]:
            url = f"https://api.telegram.org/bot{CFG['TELEGRAM_BOT_TOKEN']}/sendDocument"
            #print(CFG['TELEGRAM_BOT_TOKEN'], chat_id)
            # Name the file based on the subject
            filename = f"{mail_subject.replace(' ', '_')}.pdf"

            payload = {
                "chat_id": chat_id,
                "caption": mail_subject # The text shown with the file
            }
            files = {
                "document": (filename, pdf_file, "application/pdf")
            }

            res = requests.post(url, data=payload, files=files)
            print(res)
            # Reset pointer for the next person in the loop
            pdf_file.seek(0)

            if res.status_code != 200:
                raise RuntimeError(f"Telegram PDF Error: {res.text}")

    except Exception as e:
        raise RuntimeError(f"Failed to generate/send PDF: {str(e)}")


if __name__ == "__main__":
    ## 1. Parse the Config File
    CFG = configparse.parse("arxivnotify.cfg")

    #  Check to see if any confiuration values are missing
    if "KEYWORD" not in CFG:
        raise ValueError(
            "No keywords in the configuration file! Add one or more keywords using the 'KEYWORD' field in the config file"
        )
    if type(CFG["KEYWORD"]) is not list:
        # If there is only one keyword, make it into a list
        CFG["KEYWORD"] = [CFG["KEYWORD"]]
    if "HISTORY_DAYS" not in CFG:
        print("WARNING: No history length set in the configuration. Setting to default of 1 day.")
        CFG["HISTORY_DAYS"] = "1"
    if "TELEGRAM_BOT_TOKEN" not in CFG:
        raise ValueError(
            "No TELEGRAM_BOT_TOKEN specified! Specity it using the 'TELEGRAM_BOT_TOKEN' field in the config file"
        )
    if "TELEGRAM_CHAT_IDS" not in CFG:
        raise ValueError(
            "No TELEGRAM_CHAT_IDS specified! Specity it using the 'TELEGRAM_CHAT_IDS' field in the config file"
        )
    if "OLLAMA_HOST" not in CFG:
        raise ValueError(
            "No OLLAMA_HOST specified! Specity it using the 'OLLAMA_HOST' field in the config file"
        )
    if "OLLAMA_MODEL" not in CFG:
        raise ValueError(
            "No OLLAMA_MODEL specified! Specity it using the 'OLLAMA_MODEL' field in the config file"
        )
    if type(CFG["TELEGRAM_CHAT_IDS"]) is not list:
        # If there is only one destination meail, make it into a list
         CFG["TELEGRAM_CHAT_IDS"] = [CFG["TELEGRAM_CHAT_IDS"]]

    ## 2. Build the HTML email by quering ArXiV
    all_results = []
    try:
        num_articles = 0
        html_output = ""
        for keyword in CFG["KEYWORD"]:
            print("Parsing Keyword: {}".format(keyword))
            # Recuperiamo i dati
            queries = fetch_queries([keyword], CFG["HISTORY_DAYS"])
            if not queries:
                print("No articles found for {}, skipping...".format(keyword))
                continue
            # Aggiungiamo ai risultati globali per Ollama
            all_results.extend(queries)
            # Costruzione HTML per questa Keyword
            html_output += f"<h3>{keyword}</h3>\n"
            html_output += "<ul>\n"
            for q in queries:
                num_articles += 1
                # Unpacking della tupla per chiarezza (6 elementi)
                # title=q[0], link=q[1], abstract=q[2], date=q[3], authors=q[4], tags=q[5]
                title, link, abstract, date_obj, authors, tags = q
                html_output += "<li>\n"
                # 1. Titolo con Link
                html_output += f'\t<b><a href="{link}">{title}</a></b><br>\n'
                # 2. Badge dei Tags (Categorie)
                html_output += '\t<div class="tag-container">\n'
                for tag in tags.split(", "):
                    html_output += f'\t\t<span class="tag">{tag}</span>\n'
                html_output += '\t</div>\n'
                # 3. Autori (in corsivo con classe per CSS)
                html_output += f'\t<i class="authors">{authors}</i><br>\n'
                # 4. Data (formattata meglio)
                html_output += f'\t<span class="date">{date_obj.strftime("%Y-%m-%d")}</span>\n'
                # Se vuoi riattivare l'abstract nel PDF, decommenta sotto:
                html_output += f"<p class='abstract'>{abstract}</p>\n"
                html_output += "</li><br>\n"

            html_output += "</ul>\n"

        # Soggetto dell'email/messaggio
        mail_subject = "ArXiv Report - {} - {} New Articles".format(
            datetime.date.today().strftime("%B %d, %Y"), num_articles
        )
    except Exception:
        raise RuntimeError(
            "There was an error fetching data from the ArXiV server! Check to make sure you are connected to the internet!"
        )

    ## Add the summary:
    #summary = _summarize(all_results, CFG["KEYWORD"])
    html_output = f"""<h2> ArXiVAI Bot Email - {datetime.date.today().strftime("%B %d, %Y")}</h2>
<h2> Your Research Summary </h2>
{html_output}
"""
    #html_output = f"""<h2> ArXiVAI Bot Email - {datetime.date.today().strftime("%B %d, %Y")}</h2>
    #<h2> Your Research Summary </h2>
    #{summary}
    #{html_output}
    #"""


    ## 3. Invio del PDF tramite Telegram
    try:
        print(f"Generazione PDF e invio a Telegram in corso...")
        _send_telegram_pdf(mail_subject, html_output)
        print("Invio completato con successo!")
    except Exception as e:
        raise RuntimeError(
            f"Arxiv notifier bot non è riuscito a inviare il PDF su Telegram! Errore: {e}"
        )
