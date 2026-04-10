import com.sap.gateway.ip.core.customdev.util.Message;
import java.util.HashMap;
import java.io.*;


 
/* def Message processData(Message message) {
//get Body
	def body = message.getBody(java.lang.String) as String;
 
//replaceNamespace tag
	body = body.replaceAll("xmlns:n0=\"urn:sapappl:o2c:cp:eame:exportdeliveries:delivery:620\" xmlns:prx=\"urn:sap.com:proxy:P1B:/1SAI/TAS00000000000000000003:750\"", ""); 
	body = body.replaceAll("xmlns:n0=\"urn:sapappl:o2c:cp:eame:exportdeliveries:delivery:620\"", "");
	body = body.replaceAll("xmlns:a=\"urn:sapappl:o2c:cp:eame:exportdeliveries:delivery:620\"", "");
	
//set body
	message.setBody(body); 
	return message;
}
*/
def Message processData(Message message) {
//get Body
	def body = message.getBody(java.lang.String) as String;
	
	//body = body.replaceAll(/<MicExportRequestMessage[^>]*xmlns:soapenv="[^"]*"[^>]*>/, '<MicExportRequestMessage>')
	
	body = body.replaceAll(" xmlns:n0=\"urn:sapappl:o2c:cp:eame:exportdeliveries:delivery:620\" xmlns:prx=\"urn:sap.com:proxy:P1B:/1SAI/TAS00000000000000000003:750\" xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\"", ""); 
	body = body.replaceAll("xmlns:n0=\"urn:sapappl:o2c:cp:eame:exportdeliveries:delivery:620\"", "");
	body = body.replaceAll("xmlns:a=\"urn:sapappl:o2c:cp:eame:exportdeliveries:delivery:620\"", "");
	
//set body
	message.setBody(body); 
	return message;
}