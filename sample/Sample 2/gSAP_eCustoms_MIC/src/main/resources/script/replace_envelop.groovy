import com.sap.gateway.ip.core.customdev.util.Message;
import java.util.HashMap;
import java.io.*;


def Message processData(Message message) {

	def body = message.getBody(java.lang.String) as String;
	
	
	
	body = body.replaceAll("<SOAP-ENV:Envelope xmlns:SOAP-ENV=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:SOAP-ENC=\"http://schemas.xmlsoap.org/soap/encoding/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" ><SOAP-ENV:Body>", ""); 
	body = body.replaceAll("</SOAP-ENV:Body></SOAP-ENV:Envelope>", "");
	
	body = body.replaceAll("<m:sendData xmlns:m=\"http://service.aes.cust.mic.at\">","<m:sendData xmlns:m=\"http://service.aes.cust.mic.at\" xmlns:SOAP-ENC=\"http://schemas.xmlsoap.org/soap/encoding/\" xmlns:SOAP-ENV=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">")
		
//set body
	message.setBody(body); 
	return message;
}