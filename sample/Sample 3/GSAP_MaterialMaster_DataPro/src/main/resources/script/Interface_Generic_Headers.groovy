import com.sap.gateway.ip.core.customdev.util.Message;

def Message processData(Message message) 
{
	def messageLog = messageLogFactory.getMessageLog(message);
	if(messageLog != null)
		{
			def Country = message.getHeaders().get("Country");        
			if(Country!=null)
				{
					messageLog.addCustomHeaderProperty("Country", Country);        
        			}
			
			def Region = message.getHeaders().get("Region");        
			if(Region!=null)
				{
					messageLog.addCustomHeaderProperty("Region", Region);        
        			}
			
			def BusinessObject = message.getHeaders().get("BusinessObject");        
			if(BusinessObject!=null)
				{
					messageLog.addCustomHeaderProperty("BusinessObject", BusinessObject);        
				}

			def Sender = message.getHeaders().get("Sender");        
			if(Sender!=null)
				{
					messageLog.addCustomHeaderProperty("Sender", Sender);        
				}
        
			def Receiver = message.getHeaders().get("Receiver");        
			if(Receiver!=null)
				{
					messageLog.addCustomHeaderProperty("Receiver", Receiver);        
				}
			
			def TimeStamp = message.getHeaders().get("TimeStamp");        
        		if(TimeStamp!=null)
				{
					messageLog.addCustomHeaderProperty("TimeStamp", TimeStamp);        
				}
			def MaterialNumber = message.getHeaders().get("MaterialNumber");        
        		if(MaterialNumber!=null)
				{
					messageLog.addCustomHeaderProperty("MaterialNumber", MaterialNumber);        
				}
				def IDocNumber = message.getHeaders().get("IDocNumber");        
        		if(IDocNumber!=null)
				{
					messageLog.addCustomHeaderProperty("IDocNumber", IDocNumber);        
				}
		}

		return message;
}