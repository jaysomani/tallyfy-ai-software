# flask_server.py
from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET
import requests
import logging
import os
import time
from dotenv import load_dotenv
from datetime import datetime
import json
# Import your websocket server
from websocket_server import start_websocket_server
from collections import defaultdict
from backend import db_connector
from backend.db_connector import AwsDbConnector # noqa: F401
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("tally_connector.log")]
)
logger = logging.getLogger(__name__)
load_dotenv()
TALLY_URL = os.getenv("TALLY_URL", "http://localhost:9000")

app = Flask(__name__)

@app.route('/api/tallyConnector', methods=['POST'])
def tally_connector():
    try:
        data = request.get_json()
        logger.info(f"Received full JSON data: {json.dumps(data, indent=2)}")
        company_id = data.get("company")
        logger.info(f"Company ID from JSON: '{company_id}'")
        if not company_id:
            logger.error("Company ID missing in JSON.")
            return jsonify({"error": "Company ID missing"}), 400

        # Dynamically fetch the exact company_name using your AwsDbConnector
        real_company_name = db_connector.get_company_name_by_id(company_id)
        logger.info(f"Fetched company name from DB: '{real_company_name}' for company_id '{company_id}'")
        if not real_company_name:
            logger.error(f"Company '{company_id}' not found in database.")
            return jsonify({"error": f"Company '{company_id}' not found in database"}), 400
        # Accept data using either "data" or "journalData" key
        #transactions = data.get("data") or data.get("journalData")
        #logger.info(f"Received request for company: {company}")
        #logger.info(f"Number of transactions: {len(transactions) if transactions else 0}")
        if data.get("journalData"):
            transactions = data["journalData"]
            xml_payload = process_journals_to_xml(real_company_name, transactions)
        elif data.get("ledgerData"):
            transactions = data["ledgerData"]
            xml_payload = process_Excelledgers_to_xml(real_company_name, transactions)       
        elif data.get("data"):
            transactions = data["data"]
            xml_payload = process_ledgers_to_xml(real_company_name, transactions)
        else:
            return jsonify({"error": "Invalid data format provided"}), 400
        if not real_company_name or not transactions:
            return jsonify({"error": "Missing required data"}), 400

        xml_str = xml_payload.decode('utf-8')
        logger.info(f"XML Payload to Tally:\n{xml_str}")
        print("XML Payload to Tally:\n", xml_str)

        response = requests.post(
            TALLY_URL,
            data=xml_payload,
            headers={"Content-Type": "text/xml"},
            timeout=10
        )

        logger.info(f"Tally Response: {response.text}")
        if "LINEERROR" in response.text:
            return jsonify({"error": "Tally error", "details": response.text}), 400

        return jsonify({
            "message": "Data sent to Tally successfully",
            "transactionsProcessed": len(transactions),
            "tallyResponse": response.text
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending to Tally: {str(e)}")
        return jsonify({"error": "Failed to send data to Tally", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        return jsonify({"error": "Server error", "details": str(e)}), 500
        
        # Process the transactions (either ledger or journal entries) to XML
        xml_payload = process_ledgers_to_xml(real_company_name, transactions)
        try:
            response = requests.post(
                TALLY_URL,
                data=xml_payload,
                headers={"Content-Type": "text/xml"},
                timeout=10
            )
            logger.info(f"Tally Response: {response.text}")
            logger.error(f"Tally LINEERROR: {response.text}")
            if "LINEERROR" in response.text:
                return jsonify({"error": "Tally error", "details": response.text}), 400
            return jsonify({
                "message": "Data sent to Tally successfully",
                "transactionsProcessed": len(transactions),
                "tallyResponse": response.text
            })
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to Tally: {str(e)}")
            return jsonify({"error": "Failed to send data to Tally", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        return jsonify({"error": "Server error", "details": str(e)}), 500


def process_ledgers_to_xml(real_company_name, transactions):
    try:
        envelope = ET.Element("ENVELOPE")
        header = ET.SubElement(envelope, "HEADER")
        ET.SubElement(header, "TALLYREQUEST").text = "Import Data"
        body = ET.SubElement(envelope, "BODY")
        importdata = ET.SubElement(body, "IMPORTDATA")
        requestdesc = ET.SubElement(importdata, "REQUESTDESC")
        ET.SubElement(requestdesc, "REPORTNAME").text = "Vouchers"
        staticvars = ET.SubElement(requestdesc, "STATICVARIABLES")
        logging.info(f"Using company name: {real_company_name}")
        ET.SubElement(staticvars, "SVCURRENTCOMPANY").text = real_company_name
        requestdata = ET.SubElement(importdata, "REQUESTDATA")
        for trans in transactions:
            tallymessage = ET.SubElement(requestdata, "TALLYMESSAGE")
            tallymessage.set("xmlns:UDF", "TallyUDF")
            voucher = ET.SubElement(tallymessage, "VOUCHER")
            vch_type = "Receipt" if trans.get("transaction_type") == "receipt" else "Payment"
            voucher.set("VCHTYPE", vch_type)
            voucher.set("ACTION", "Create")
            voucher.set("OBJVIEW", "Accounting Voucher View")
            date_str = trans.get("transaction_date", "")
            if date_str:
                formatted_date = date_str.replace("-", "")
                ET.SubElement(voucher, "DATE").text = formatted_date
            ET.SubElement(voucher, "VOUCHERTYPENAME").text = vch_type
            ET.SubElement(voucher, "NARRATION").text = trans.get("description", "")
            ET.SubElement(voucher, "VOUCHERNUMBER").text = str(trans.get("id", ""))
            amount = float(trans.get("amount", 0))
            bank_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(bank_entry, "LEDGERNAME").text = trans.get("bank_account", "")
            is_payment = vch_type == "Payment"
            ET.SubElement(bank_entry, "ISDEEMEDPOSITIVE").text = "Yes" if is_payment else "No"
            ET.SubElement(bank_entry, "AMOUNT").text = f"{-amount:.2f}"
            ledger_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(ledger_entry, "LEDGERNAME").text = trans.get("assigned_ledger", "")
            ET.SubElement(ledger_entry, "ISDEEMEDPOSITIVE").text = "No" if is_payment else "Yes"
            ET.SubElement(ledger_entry, "AMOUNT").text = f"{amount:.2f}"
        xml_bytes = ET.tostring(envelope, encoding="utf-8", method="xml", xml_declaration=True)
        return xml_bytes
    except Exception as e:
        logger.error(f"Error in process_ledgers_to_xml: {str(e)}")
        raise

def process_journals_to_xml(real_company_name, transactions):
    envelope = ET.Element("ENVELOPE")

    header = ET.SubElement(envelope, "HEADER")
    ET.SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = ET.SubElement(envelope, "BODY")
    importdata = ET.SubElement(body, "IMPORTDATA")

    requestdesc = ET.SubElement(importdata, "REQUESTDESC")
    ET.SubElement(requestdesc, "REPORTNAME").text = "Vouchers"

    staticvars = ET.SubElement(requestdesc, "STATICVARIABLES")
    ET.SubElement(staticvars, "SVCURRENTCOMPANY").text = real_company_name

    requestdata = ET.SubElement(importdata, "REQUESTDATA")

    grouped_transactions = defaultdict(list)
    for trans in transactions:
        grouped_transactions[trans['journal_no']].append(trans)

    for journal_no, entries in grouped_transactions.items():
        tallymessage = ET.SubElement(requestdata, "TALLYMESSAGE")
        tallymessage.set("xmlns:UDF", "TallyUDF")

        voucher = ET.SubElement(tallymessage, "VOUCHER")
        voucher.set("VCHTYPE", "Journal")
        voucher.set("ACTION", "Create")

        date_str = entries[0]['date'][:10].replace("-", "")
        ET.SubElement(voucher, "DATE").text = date_str
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Journal"
        ET.SubElement(voucher, "VOUCHERNUMBER").text = entries[0]['journal_no']

        # Adding the PERSISTEDVIEW as per your provided sample XML
        ET.SubElement(voucher, "PERSISTEDVIEW").text = "Accounting Voucher View"

        # OPTIONAL: PARTYLEDGERNAME, include only if there's a suitable ledger
        # ET.SubElement(voucher, "PARTYLEDGERNAME").text = entries[0]['particulars']

        # Removed REFERENCE tag intentionally
        ET.SubElement(voucher, "NARRATION").text = entries[0]['narration'] or ''

        for entry in entries:
            ledger_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(ledger_entry, "LEDGERNAME").text = entry['particulars']

            is_positive = "No" if entry['dr_cr'] == "Dr" else "Yes"
            amount_value = float(entry['amount'])

            ET.SubElement(ledger_entry, "ISDEEMEDPOSITIVE").text = is_positive
            amount_formatted = f"{-amount_value:.2f}" if is_positive == "Yes" else f"{amount_value:.2f}"
            ET.SubElement(ledger_entry, "AMOUNT").text = amount_formatted

            if entry.get('ledger_narration'):
                ET.SubElement(ledger_entry, "NARRATION").text = entry['ledger_narration']

    xml_bytes = ET.tostring(envelope, encoding="utf-8", method="xml", xml_declaration=True)
    return xml_bytes


def process_Excelledgers_to_xml(real_company_name, ledger_data):
    try:
        envelope = ET.Element("ENVELOPE")

        header = ET.SubElement(envelope, "HEADER")
        ET.SubElement(header, "TALLYREQUEST").text = "Import Data"

        body = ET.SubElement(envelope, "BODY")
        importdata = ET.SubElement(body, "IMPORTDATA")

        requestdesc = ET.SubElement(importdata, "REQUESTDESC")
        ET.SubElement(requestdesc, "REPORTNAME").text = "All Masters"

        staticvars = ET.SubElement(requestdesc, "STATICVARIABLES")
        ET.SubElement(staticvars, "SVCURRENTCOMPANY").text = real_company_name

        requestdata = ET.SubElement(importdata, "REQUESTDATA")

        for ledger in ledger_data:
            tallymessage = ET.SubElement(requestdata, "TALLYMESSAGE")
            tallymessage.set("xmlns:UDF", "TallyUDF")

            ledger_xml = ET.SubElement(tallymessage, "LEDGER", NAME=ledger["name"], ACTION="Create")

            ET.SubElement(ledger_xml, "NAME").text = ledger["name"]
            ET.SubElement(ledger_xml, "PARENT").text = ledger["parent"]
            ET.SubElement(ledger_xml, "MAILINGNAME").text = ledger.get("mailing_name", ledger["name"])

            if ledger.get("bill_by_bill") == "Yes":
                ET.SubElement(ledger_xml, "BILLBYBILL").text = "Yes"

            ET.SubElement(ledger_xml, "GSTREGISTRATIONTYPE").text = ledger.get("registration_type", "Unknown")

            # Additional fields based on your received data
            ET.SubElement(ledger_xml, "GSTAPPLICABLE").text = ledger.get("gst_applicable", "Not Applicable")
            ET.SubElement(ledger_xml, "GSTTYPEOFSUPPLY").text = ledger.get("taxability", "Unknown")

            if ledger.get("set_alter_gst_details") == "Yes":
                gst_details = ET.SubElement(ledger_xml, "GSTDETAILS.LIST")
                ET.SubElement(gst_details, "APPLICABLEFROM").text = ledger.get("applicable_date", "")
                ET.SubElement(gst_details, "TAXABILITY").text = ledger.get("taxability", "Unknown")
                ET.SubElement(gst_details, "STATEWISEDETAILS.LIST")

            ET.SubElement(ledger_xml, "INVENTORYVALUESAREAFFECTED").text = ledger.get("inventory_affected", "No")
            ET.SubElement(ledger_xml, "CREDITPERIOD").text = ledger.get("credit_period", "")

            if ledger.get("address"):
                ET.SubElement(ledger_xml, "ADDRESS").text = ledger["address"]
            if ledger.get("state"):
                ET.SubElement(ledger_xml, "STATENAME").text = ledger["state"]
            if ledger.get("pincode"):
                ET.SubElement(ledger_xml, "PINCODE").text = ledger["pincode"]

            if ledger.get("pan_it_no"):
                ET.SubElement(ledger_xml, "INCOMETAXNUMBER").text = ledger["pan_it_no"]

            if ledger.get("gstin_uin"):
                ET.SubElement(ledger_xml, "PARTYGSTIN").text = ledger["gstin_uin"]

        xml_bytes = ET.tostring(envelope, encoding="utf-8", method="xml", xml_declaration=True)
        return xml_bytes

    except Exception as e:
        logger.error(f"Error in process_ledgers_to_xml: {str(e)}")
        raise


if __name__ == "__main__":
    # Start the WebSocket server in a separate thread
    from threading import Thread
    ws_thread = Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    time.sleep(1)
    app.run(host="0.0.0.0", port=5000)