import com.sap.gateway.ip.core.customdev.util.Message;
import java.util.HashMap;
import java.text.SimpleDateFormat;


// Save SAP Quotation Payload
def Message logPayloadSAP(Message message) {
    
    def body = message.getBody(java.lang.String) as String;
	def messageLog = messageLogFactory.getMessageLog(message);
	
	messageLog.addAttachmentAsString("1# SAP Quotation Payload", body, "text/xml");
		
	return message;
}

// Save Payload after SFDC Look-Up
def Message logLookUpSFDC(Message message) {
    
    def body = message.getBody(java.lang.String) as String;
	def messageLog = messageLogFactory.getMessageLog(message);
	
	messageLog.addAttachmentAsString("2# LookUP SFDC", body, "text/plain");
		
	return message;
}

// Save Payload after Map to XSD SAP Proxy
def Message logMapSFDC(Message message) {
    
    def body = message.getBody(java.lang.String) as String;
	def messageLog = messageLogFactory.getMessageLog(message);
	
	messageLog.addAttachmentAsString("2# Map SFDC Query", body, "text/xml");
		
	return message;
}

// Log Error
def Message logError(Message message) {
    
    def body = message.getBody(java.lang.String) as String;
	def messageLog = messageLogFactory.getMessageLog(message);
	
	messageLog.addAttachmentAsString("Error Log", body, "text/xml");
		
	return message;
}

//Method to disable log attached
def Message logDisable(Message message) {
	return message;
}