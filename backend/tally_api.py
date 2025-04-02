# tally_api.py
import time
import re
import logging
import requests
import xml.etree.ElementTree as ET
from lxml import etree as LET  # Requires: pip install lxml
from backend.config import TALLY_URL  # TALLY_URL is defined in config.py

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TallyAPIError(Exception):
    """Custom exception for Tally API errors."""
    pass

class TallyAPI:
    def __init__(self, server_url=None, cache_timeout=10):
        self.server_url = server_url or TALLY_URL
        self.cache_timeout = cache_timeout
        self.cache = {}  # For dynamic fetch_data caching
        # Cache for get_active_company
        self.company_cache = None
        self.company_cache_time = 0

    def is_tally_running(self):
        try:
            response = requests.get(self.server_url, timeout=3)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def send_request(self, xml_request):
        if not self.is_tally_running():
            logging.error("Tally is not accessible.")
            return None
        try:
            response = requests.post(
                self.server_url, data=xml_request, headers={"Content-Type": "text/xml"}
            )
            response.raise_for_status()
            return self.clean_xml(response.text)
        except requests.exceptions.RequestException as e:
            logging.error(f"Tally request error: {e}")
            return None

    @staticmethod
    def clean_xml(text):
        # Remove non-printable and unwanted characters
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        cleaned = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\xA0-\xD7FF\xE000-\xFFFD]', '', cleaned)
        
        # Replace numeric character references with their actual character if allowed
        def replace_entity(match):
            try:
                num_str = match.group(1)
                if num_str.lower().startswith('x'):
                    code = int(num_str[1:], 16)
                else:
                    code = int(num_str)
                # Allow allowed XML characters: Tab, newline, carriage return, and other allowed ranges.
                if code in (0x09, 0x0A, 0x0D) or (0x20 <= code <= 0xD7FF) or (0xE000 <= code <= 0xFFFD):
                    return chr(code)
                else:
                    return ''
            except Exception:
                return ''
        cleaned = re.sub(r'&#(x?[0-9A-Fa-f]+);', replace_entity, cleaned)
        
        # Extract only the ENVELOPE content
        cleaned = re.sub(r'^.*?<ENVELOPE>', '<ENVELOPE>', cleaned, 1, re.DOTALL)
        cleaned = re.sub(r'</ENVELOPE>.*$', '</ENVELOPE>', cleaned, 1, re.DOTALL)
        return cleaned.strip()

    def _generate_request(self, request_type, request_id, fetch_fields=None, collection_type="Ledger"):
        fields_xml = f"<FETCH>{', '.join(fetch_fields)}</FETCH>" if fetch_fields else ""
        return f"""
        <ENVELOPE>
            <HEADER>
                <VERSION>1</VERSION>
                <TALLYREQUEST>Export</TALLYREQUEST>
                <TYPE>{request_type}</TYPE>
                <ID>{request_id}</ID>
            </HEADER>
            <BODY>
                <DESC>
                    <STATICVARIABLES>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                    <TDL>
                        <TDLMESSAGE>
                            <COLLECTION NAME="{request_id}" ISMODIFY="No">
                                <TYPE>{collection_type}</TYPE>
                                {fields_xml}
                            </COLLECTION>
                        </TDLMESSAGE>
                    </TDL>
                </DESC>
            </BODY>
        </ENVELOPE>
        """.strip()

    def get_active_company(self, use_cache=True):
        """
        Retrieves the active company from Tally.
        This method is preserved as-is.
        """
        current_time = time.time()
        if use_cache and self.company_cache and (current_time - self.company_cache_time) < self.cache_timeout:
            return self.company_cache
        xml_request = self._generate_request("Function", "$$CurrentCompany")
        response_xml = self.send_request(xml_request)
        if not response_xml:
            return "Unknown (Tally not responding)"
        try:
            root = ET.fromstring(response_xml)
            company = root.findtext(".//RESULT", "Unknown")
            self.company_cache = company
            self.company_cache_time = current_time
            return company
        except ET.ParseError as e:
            logging.error(f"Failed to parse Tally response: {e}")
            return "Unknown (Parsing Error)"

    def fetch_data(self, request_id, collection_type="Ledger", fetch_fields=None, use_cache=True):
        """
        Dynamically fetch data from Tally based on provided fields.
        This method uses dynamic field selection and robust XML parsing.
        """
        current_time = time.time()
        cache_key = request_id
        if use_cache and cache_key in self.cache and (current_time - self.cache[cache_key][0]) < self.cache_timeout:
            return self.cache[cache_key][1]

        xml_request = self._generate_request(
            "Collection", request_id, fetch_fields=fetch_fields, collection_type=collection_type
        )

        response_xml = self.send_request(xml_request)
        extracted_data = []

        if response_xml:
            try:
                root = ET.fromstring(response_xml)
            except ET.ParseError as e:
                logging.error(f"XML Parsing error with ElementTree: {e}")
                logging.info("Attempting to parse using lxml with recovery mode.")
                try:
                    parser = LET.XMLParser(recover=True)
                    root = LET.fromstring(response_xml.encode('utf-8'), parser=parser)
                except Exception as e2:
                    logging.error(f"XML Parsing error with lxml: {e2}")
                    return extracted_data

            for item in root.findall(f".//COLLECTION/{collection_type.upper()}"):
                # Build dictionary only with requested fields
                item_data = {
                    field: (item.findtext(field.upper(), "N/A") or "N/A").strip()
                    for field in fetch_fields
                }
                # If the XML attribute "NAME" exists, use that as the normalized "Name"
                item_name = item.get("NAME")
                if item_name:
                    item_data["Name"] = item_name
                # Only normalize "ClosingBalance" if it was requested
                if "CLOSINGBALANCE" in fetch_fields:
                    if "CLOSINGBALANCE" in item_data and "ClosingBalance" not in item_data:
                        item_data["ClosingBalance"] = item_data["CLOSINGBALANCE"]
                extracted_data.append(item_data)

            self.cache[request_id] = (time.time(), extracted_data)
            logging.info(f"Fetched data ({collection_type}): {extracted_data}")

        return extracted_data

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    tally = TallyAPI()
    # Example: Fetch active company (existing functionality)
    active_company = tally.get_active_company(use_cache=False)
    print("Active Company:", active_company)
    
    # Example: Dynamic fetching for ledger data with custom fields.
    selected_company_request_id = "SelectedCompany"  # Replace with your actual request ID
    # Here, we choose NOT to include CLOSINGBALANCE
    fetch_fields = ["LEDGERNAME", "PARENT"]
    extracted_data = tally.fetch_data(
        request_id=selected_company_request_id,
        collection_type="Ledger",
        fetch_fields=fetch_fields,
        use_cache=False
    )
    print("Extracted Data for Selected Company in Tally:")
    for record in extracted_data:
        print(record)
