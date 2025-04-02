' Save this code as FetchCompanies.vbs

'--- Construct the XML request ---
Dim strRequestXML
strRequestXML = _
    "<ENVELOPE>" & _
    "  <HEADER>" & _
    "    <TALLYREQUEST>Export Data</TALLYREQUEST>" & _
    "  </HEADER>" & _
    "  <BODY>" & _
    "    <EXPORTDATA>" & _
    "      <REQUESTDESC>" & _
    "        <REPORTNAME>List of Companies</REPORTNAME>" & _
    "        <STATICVARIABLES>" & _
    "          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>" & _
    "        </STATICVARIABLES>" & _
    "      </REQUESTDESC>" & _
    "    </EXPORTDATA>" & _
    "  </BODY>" & _
    "</ENVELOPE>"

'--- Create an XML HTTP object ---
Dim objXMLHTTP
Set objXMLHTTP = CreateObject("Msxml2.ServerXMLHTTP.6.0")

'--- Open connection to Tally ---
' Change "127.0.0.1" to the IP address where Tally is running
' Ensure that the port (e.g., 9000) matches Tally's configuration for XML requests
objXMLHTTP.open "POST", "http://localhost:9000", False

'--- Send the XML request ---
objXMLHTTP.send strRequestXML

'--- Retrieve the XML response from Tally ---
Dim strResponseXML
strResponseXML = objXMLHTTP.responseText

'--- Display the response (which should contain the list of companies) ---
MsgBox "Response from Tally:" & vbCrLf & strResponseXML

'--- Clean up ---
Set objXMLHTTP = Nothing