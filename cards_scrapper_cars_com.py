import pymysql

from bs4 import BeautifulSoup
import requests
import time
import json
import os


start_time = time.time()
start_time_str = time.strftime("%Y-%m-%d-%H-%M-%S", time.gmtime(start_time))

headers = requests.utils.default_headers()
headers.update({
    "Accept-Encoding": "gzip, deflate, sdch",
    "Accept-Language": "en-US,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "TGTG/22.2.1 Dalvik/2.1.0 (Linux; U; Android 9; SM-G955F Build/PPR1.180610.011)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive"
})

DEFAULT_HEADER = headers #{'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

# SITE_URL = "https://www.cars.com"

def get_parsed_card(url, debug=0, headers=DEFAULT_HEADER):
    card_dict = {}

    page = requests.get(url, headers=headers)

    if page.status_code == 200:
        soup = BeautifulSoup(page.text, "html.parser")

        card = soup.find("section", class_="listing-overview")
        # print(card,"\n")
        if card == None:
            return {} # {} - empty result

        card_gallery = card.find("div", class_="modal-slides-and-controls")
        card_dict["gallery"] = []
        try:
            for img in card_gallery.find_all("img", class_="swipe-main-image"):
                card_dict["gallery"].append(img["src"])
        except:
            pass

        basic_content = soup.find("div", class_="basics-content-wrapper")

        basic_section = basic_content.find("section", class_="sds-page-section basics-section")
        fancy_description_list = basic_section.find("dl", class_="fancy-description-list")
        dt_elements = [elem.text.strip() for elem in fancy_description_list.find_all("dt")]
        dd_elements = [elem.get_text(separator='|', strip=True).split("|")[0] for elem in fancy_description_list.find_all("dd")]
        for key, value in zip(dt_elements, dd_elements):
            card_dict[key.lower()] = value

        card_dict["card_id"] = card_dict.get("stock #")
        if not card_dict["card_id"] or card_dict["card_id"] == "-":
            card_dict["card_id"] = card_dict.get("vin")
        if not card_dict["card_id"] or card_dict["card_id"] == "-":
            return {}

        card_dict["url"] = url

        card_title = card.find(class_="listing-title")
        card_dict["title"] = card_title.text

        card_price_primary = card.find("div", class_="price-section")
        card_dict["price_primary"] = card_price_primary.find("span", class_="primary-price").text

        price_history = ""
        card_price_history = soup.find("div", class_="price-history")
        try:
            card_price_history_rows = card_price_history.find_all("tr")
            for row in card_price_history_rows:
                date, _, price = row.find_all("td")
                price_history += f"{date.text}: {price.text} | "

            card_dict["price_history"] = price_history[0:-2]
        except:
            card_dict["price_history"] = ""

        card_dict["options"] = []
        try:
            feature_content = basic_content.find("section", class_="sds-page-section features-section")
            fancy_description_list = feature_content.find("dl", class_="fancy-description-list")
            dt_elements = [elem.text.strip() for elem in fancy_description_list.find_all("dt")]
            dd_elements = [elem.get_text(separator='|', strip=True).split("|") for elem in fancy_description_list.find_all("dd")]
            for category, values in zip(dt_elements, dd_elements):
                section_dict = {}
                section_dict["category"] = category
                section_dict["items"] = values

                card_dict["options"].append(section_dict)

            all_features = basic_content.find("div", class_="all-features-text-container")
            section_dict = {}
            section_dict["category"] = "features"
            section_dict["items"] = all_features.get_text("|", True).split("|")
            card_dict["options"].append(section_dict)
        except:
            pass


        try:
            card_vehicle_history = basic_content.find("section", class_="sds-page-section vehicle-history-section")
            fancy_description_list = card_vehicle_history.find("dl", class_="fancy-description-list")
            dt_elements = [elem.text.strip() for elem in fancy_description_list.find_all("dt")]
            dd_elements = [elem.get_text(separator='|', strip=True) for elem in fancy_description_list.find_all("dd")]
            vehicle_history = ""
            for record, value in zip(dt_elements, dd_elements):
                vehicle_history += f"{record}: {value} | "

            card_dict["vehicle_history"] = vehicle_history[0:-2]
        except:
            card_dict["vehicle_history"] = ""

        card_comment = basic_content.find("div", class_="sellers-notes")
        try:
            card_dict["comment"] = card_comment.get_text(separator="|", strip=True).replace("\n", "|")
        except:
            card_dict["comment"] = ""

        card_location = basic_content.find("div", class_="dealer-address")
        try:
            card_dict["location"] = card_location.text
        except:
            card_dict["location"] = ""

        card_labels_div = card.find("div", class_="vehicle-badging")
        data_override_payload_json = json.loads(card_labels_div["data-override-payload"])
        card_dict["bodystyle"] = data_override_payload_json["bodystyle"]

        labels = []
        try:
            for div in card_labels_div.find_all("span", class_="sds-badge__label"):
                labels += [div.text]

            labels += ["VIN: " + card_dict["vin"]]

            if basic_content.find("section", "sds-page-section warranty_section"):
                labels += ["Included warranty"]
        except:
            pass
        card_dict["labels"] = "|".join(labels)

        mpg = ""
        try:
            mpg = card_dict.get("mpg").strip().replace('0–0', "")
            if mpg == "–":
                mpg = ""
        except:
            pass

        card_dict["description"] = card_dict["title"].split()[0] + ", " + \
                                   card_dict["transmission"].replace(",", " ") + ", " + \
                                   card_dict["engine"].replace(",", " ") + ", " + \
                                   card_dict["fuel type"].replace(",", " ") + \
                                   ((" (" + mpg + " mpg)") if mpg else "") + ", " + \
                                   card_dict["mileage"].replace(",", " ") +" | " + \
                                   card_dict["bodystyle"].replace(",", " ") + ", " + \
                                   card_dict["drivetrain"].replace(",", " ") + ", " + \
                                   card_dict["exterior color"].replace(",", " ")

        del card_dict["transmission"]
        del card_dict["engine"]
        del card_dict["fuel type"]
        del card_dict["mileage"]
        del card_dict["bodystyle"]
        del card_dict["drivetrain"]
        del card_dict["exterior color"]
        del card_dict["interior color"]
        if card_dict.get("mpg"):
            del card_dict["mpg"]
        del card_dict["vin"]
        if card_dict.get("stock #"):
            del card_dict["stock #"]

        # card_dict["exchange"] = ""

        card_dict["scrap_date"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        card_dict["json"] = card_dict.copy()

        del card_dict["url"]

    return card_dict


def make_folder(start_folder, subfolders_chain):
    folder = start_folder
    for subfolder in subfolders_chain:
        folder += "/" + subfolder
        if not os.path.isdir(folder):
            os.mkdir(folder)

    return folder



def execute_sql(con, sql_statements, fetch_mode="fetchone"):
    cur = con.cursor()
    for sql in sql_statements:
        cur.execute(sql)

    res = None
    if cur.rowcount > 0:
        if fetch_mode == "fetchone":
            res = cur.fetchone()
        else:
            res = cur.fetchall()

    return res


def audit_start(con, context):
    process_desc = context["process_desc"]
    sql_statements = [
        f"""
            insert into process_log(process_desc, user, host) 
            select '{process_desc}', user, host 
            from information_schema.processlist 
            where ID = connection_id();
        """,
        "select last_insert_id() as process_log_id;"
    ]

    return execute_sql(con, sql_statements)


def audit_end(con, context):
    process_log_id = context["process_log_id"]

    sql_statements = [f"update process_log set end_date = current_timestamp where process_log_id = {process_log_id};"]

    return execute_sql(con, sql_statements)


def find_random_cards_to_parse(con, context):
    refresh_time = context["refresh_time"]
    num = context["limit"] if context["limit"] != 0 else 999999

    while True:
        random_ads_id = execute_sql(con, ["select floor(rand() * (select max(ad_group_id) from ad_groups));"])[0]

        records_fetched = execute_sql(con,
            [
                f"""
                    with cte_random_record_group as
                    (
                        select ads_id, 
                               concat(source_id, card_url) as url, 
                               ifnull(ad_status/(1 + timestampdiff(hour, change_status_date, current_timestamp)), 0) as score
                        from car_ads_db.ads 
                        where ((ad_status = 0) or (ad_status = 2 and timestampdiff(hour, change_status_date, current_timestamp) > {refresh_time})) and
                              ad_group_id >= {random_ads_id}                              
                        limit {max(10, num)}
                    )
                    select ads_id, url 
                    from cte_random_record_group 
                    order by score 
                    limit {num};                  
                """
            ],
            fetch_mode="fetchall"
        )

        if records_fetched != None:
            break

        # check if there is still what to do
        if execute_sql(con,
                [
                    f"""
                        select 1 
                        from car_ads_db.ads 
                        where ad_status = 0 or (ad_status = 2 and timestampdiff(hour, change_status_date, current_timestamp) > {refresh_time}) 
                        limit 1;
                    """
                ]
            ) != None:
            continue

        # job is done
        break

    return records_fetched


def update_and_archive(con, context):
    ads_id = context["ads_id"]
    process_log_id = context["process_log_id"]
    ad_status = context["ad_status"]

    # archive the processed data regardless of what is its status
    execute_sql(con,
        [
            f"""
                insert into car_ads_db.ads_archive(
                    ads_id, 
                    source_id, 
                    card_url, 
                    ad_group_id, 
                    insert_process_log_id, 
                    insert_date, 
                    change_status_process_log_id, 
                    ad_status
                )
                select 
                    ads_id, 
                    source_id, 
                    card_url, 
                    ad_group_id, 
                    insert_process_log_id, 
                    insert_date, 
                    {process_log_id}, 
                    {ad_status}
                from car_ads_db.ads
                where ads_id = {ads_id}
            """
        ]
    )

    if ad_status in {1, -1}:
        # ad_status: -1 is considered as bad data, 1 - advert is no longer listed
        execute_sql(con,
            [
                f"""
                    delete from car_ads_db.ads
                    where ads_id = {ads_id}
                """
            ]
        )
    else:
        # ad_status: 2 - successfully processed. leave only such records
        execute_sql(con,
            [
                f"""
                    update car_ads_db.ads
                        set ad_status = {ad_status},
                            change_status_process_log_id = {process_log_id},
                            change_status_date = current_timestamp   
                    where ads_id = {ads_id}
                """
            ]
        )


def main():
    with open("config.json") as config_file:
        configs = json.load(config_file)

    con = pymysql.connect(**configs["audit_db"])

    make_folder(configs["folders"]["base_folder"], [configs["folders"]["scrapped_data"], "cars_com", "json", start_time_str])

    with con:
        process_log_id = audit_start(con, {"process_desc": "cards_scrapper_cars_com.py"})[0]

        cur = con.cursor()

        num = 0
        while True:
            records_fetched = find_random_cards_to_parse(con, {"limit": 1, "refresh_time": 24})

            if records_fetched == None:
                break

            for ads_id, url in records_fetched:
                num += 1

                url_parts = url.split("?")
                url_updated = url_parts[0].replace("/", "-").replace(".", "-").replace(":", "-")

                parsed_card = {}
                ad_status = 1
                year = "-"
                try:
                    if len(url_parts) == 1:
                        parsed_card = get_parsed_card(url)
                except:
                    # error when parsing the card (url)
                    ad_status = -1

                if parsed_card != {}:
                    card_id = parsed_card["card_id"]
                    try:
                        price_usd = int(parsed_card["price_primary"].replace('$', '').replace(',', ''))  # '$19,999'
                        year = parsed_card["title"].split()[0]
                        folder = make_folder(configs["folders"]["base_folder"],
                                             [
                                                 configs["folders"]["scrapped_data"],
                                                 "cars_com", "json",
                                                 f"{start_time_str}",
                                                 f"{year}",
                                                 f"price_{price_usd}-{price_usd + 9999}"
                                             ])
                        with open(f"{folder}/{url_updated}.json", "w", encoding="utf-8") as f:
                            f.write(str(parsed_card["json"]).replace("\\xa0", " ").replace("\\u2009", " "))

                        # successfully parsed the card (url)
                        ad_status = 2
                    except:
                        ad_status = -1

                update_and_archive(con, {"ads_id": ads_id , "process_log_id": process_log_id, "ad_status": ad_status})

                print(f"{time.strftime('%X', time.gmtime(time.time() - start_time))}, num: {num:>6}, {ad_status:>2}, ads_id: {ads_id:>6}, year: {year:>4}: {url}")

        audit_end(con, {"process_log_id": process_log_id})



if __name__ == "__main__":
    main()
