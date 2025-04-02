# test.py
import time
import re
import logging
import xml.etree.ElementTree as ET
from lxml import etree as LET
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuration variables (simulate your backend/config.py)
TALLY_URL = "http://localhost:9000"  # Your Tally instance URL
DEFAULT_SESSION_ID = "DEFAULT_SESSION"  # Use default session for testing (if no real login)
DEFAULT_TOKEN = 1

class TallyAPIError(Exception):
    """Custom exception for Tally API errors."""
    pass

class TallyAPI:
    def __init__(self, server_url=None, cache_timeout=10):
        self.server_url = server_url or TALLY_URL
        self.cache_timeout = cache_timeout
        self.cache = {}  # For dynamic fetch_data caching
        self.company_cache = None
        self.company_cache_time = 0
        # Set default session info for testing
        self.session_id = DEFAULT_SESSION_ID
        self.token = DEFAULT_TOKEN

    def set_session_info(self, session_id, token):
        """Store session ID and token obtained during authentication."""
        self.session_id = session_id
        self.token = token

    def is_tally_running(self):
        # For testing, we'll assume Tally is running.
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
                self.server_url,
                data=xml_request,
                headers={"Content-Type": "text/xml;charset=utf-16"}  # Use required header
            )
            response.raise_for_status()
            logging.info("RAW RESPONSE:\n%s", response.text)  # Debug: log raw response
            return self.clean_xml(response.text)
        except requests.exceptions.RequestException as e:
            logging.error(f"Tally request error: {e}")
            return None

    @staticmethod
    def clean_xml(text):
        # Remove non-printable characters
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
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
                item_data = {
                    field: (item.findtext(field.upper(), "N/A") or "N/A").strip()
                    for field in fetch_fields
                }
                item_name = item.get("NAME")
                if item_name:
                    item_data["Name"] = item_name
                if "CLOSINGBALANCE" in fetch_fields:
                    if "CLOSINGBALANCE" in item_data and "ClosingBalance" not in item_data:
                        item_data["ClosingBalance"] = item_data["CLOSINGBALANCE"]
                extracted_data.append(item_data)
            self.cache[request_id] = (time.time(), extracted_data)
            logging.info(f"Fetched data ({collection_type}): {extracted_data}")
        return extracted_data

    def get_selected_companies(self, use_cache=True):
        cache_key = "selected_companies"
        current_time = time.time()
        if use_cache and cache_key in self.cache and (current_time - self.cache[cache_key][0]) < self.cache_timeout:
            return self.cache[cache_key][1]
        
        # Build XML request using the provided specification.
        xml_request = """
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <REQVERSION>1</REQVERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>List of Companies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <TDL>
        <TDLMESSAGE>
          <REPORT NAME="List of Companies" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <FORMS>List of Companies</FORMS>
          </REPORT>
          <FORM NAME="List of Companies" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <TOPPARTS>List of Companies</TOPPARTS>
            <XMLTAG>"List of Companies"</XMLTAG>
          </FORM>
          <PART NAME="List of Companies" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <TOPLINES>List of Companies</TOPLINES>
            <REPEAT>List of Companies : Collection of Companies</REPEAT>
            <SCROLLED>Vertical</SCROLLED>
          </PART>
          <LINE NAME="List of Companies" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <LEFTFIELDS>Name</LEFTFIELDS>
          </LINE>
          <FIELD NAME="Name" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <SET>$Name</SET>
            <XMLTAG>"NAME"</XMLTAG>
          </FIELD>
          <COLLECTION NAME="Collection of Companies" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <TYPE>Company</TYPE>
            <FETCH>NAME</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
        """.strip()
        
        # Send the request. Use the default header (or adjust if necessary).
        headers = {"Content-Type": "text/xml;charset=utf-16"}
        try:
            response = requests.post(self.server_url, data=xml_request, headers=headers, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Tally request error: {e}")
            return []
        
        response_xml = self.clean_xml(response.text)
        companies = []
        if response_xml:
            try:
                root = ET.fromstring(response_xml)
                # Parse the response expected as:
                # <LISTOFCOMPANIES>
                #   <NAME>ABC Company</NAME>
                #   <NAME>Test</NAME>
                # </LISTOFCOMPANIES>
                for name_elem in root.findall(".//NAME"):
                    if name_elem.text:
                        companies.append(name_elem.text.strip())
                self.cache[cache_key] = (time.time(), companies)
                logging.info(f"Fetched selected companies: {companies}")
            except ET.ParseError as e:
                logging.error(f"Failed to parse selected companies response: {e}")
        else:
            logging.error("No response received for selected companies request.")
        return companies

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    tally = TallyAPI()
    # Set default session info for testing
    tally.set_session_info("DEFAULT_SESSION", 1)
    
    active_company = tally.get_active_company(use_cache=False)
    print("Active Company:", active_company)
    
    fetch_fields = ["LEDGERNAME", "PARENT"]
    extracted_data = tally.fetch_data(
        request_id="SelectedCompany",
        collection_type="Ledger",
        fetch_fields=fetch_fields,
        use_cache=False
    )
    print("\nExtracted Data for Selected Company in Tally:")
    for record in extracted_data:
        print(record)
    
    companies = tally.get_selected_companies(use_cache=False)
    print("\nSelected Companies:", companies)
