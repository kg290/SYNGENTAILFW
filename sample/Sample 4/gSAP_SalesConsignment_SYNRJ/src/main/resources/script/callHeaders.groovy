import com.sap.gateway.ip.core.customdev.util.Message;

def Message processData(Message message) {
    
	def messageLog = messageLogFactory.getMessageLog(message);
	if(messageLog != null){

		def Country = message.getHeaders().get("Country");		
		if(Country!=null){
			messageLog.addCustomHeaderProperty("Country", Country);		
        }
        def Region = message.getHeaders().get("Region");		
		if(Region!=null){
			messageLog.addCustomHeaderProperty("Region", Region);		
        }
        def BusinessObject = message.getHeaders().get("BusinessObject");		
		if(BusinessObject!=null){
			messageLog.addCustomHeaderProperty("BusinessObject", BusinessObject);		
        }
        def Sender = message.getHeaders().get("Sender");		
		if(Sender!=null){
			messageLog.addCustomHeaderProperty("Sender", Sender);		
        }
        def Receiver = message.getHeaders().get("Receiver");		
		if(Receiver!=null){
			messageLog.addCustomHeaderProperty("Receiver", Receiver);		
        }
         def TimeStamp = message.getHeaders().get("TimeStamp");		
		if(TimeStamp!=null){
			messageLog.addCustomHeaderProperty("TimeStamp", TimeStamp);		
        }
         def InvoiceNum = message.getHeaders().get("InvoiceNum");		
		if(InvoiceNum!=null){
			messageLog.addCustomHeaderProperty("InvoiceNum", InvoiceNum);		
        }
        def SAP_ApplicationID = message.getHeaders().get("SAP_ApplicationID");		
		if(SAP_ApplicationID!=null){
			messageLog.addCustomHeaderProperty("SAP_ApplicationID", SAP_ApplicationID);		
        }
	}
	return message;
}