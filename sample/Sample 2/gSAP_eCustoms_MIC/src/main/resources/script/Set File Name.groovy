import com.sap.gateway.ip.core.customdev.util.Message;
import java.util.*;
// String DynamicFileName(String DeliveryNumber, String timestamp, String RCVPRN) {
//     String ournewfilename = ""
 
//  if (RCVPRN == "WHS_AUM") {
//      ournewfilename = "${DeliveryNumber}_${timestamp}.S1A";
//   } else if (RCVPRN == "WHS_AUF") {
//      ournewfilename = "${DeliveryNumber}_${timestamp}.S1B";
//   } else if (RCVPRN == "WHS_DUB") {
//      ournewfilename = "sadv";
//   } else {
//      ournewfilename = "sadv";
//   }
//   return "ournewfilename"
def Message processData(Message message) {
//def body = message.getBody(Map)
//def RCVPRN = body['RCVPRN']
String RCVPRN = message.getProperty('RCVPRN');
  String DeliveryNumber = message.getProperty('DeliveryNumber');
  String TimeStamp = message.getProperty('TimeStamp');
 
  String Name='';
if(RCVPRN.equals("WHS_AUM")) {
  Name = DeliveryNumber + "_" + TimeStamp + ".S1A";
  message.setProperty("FileName1", Name);
println(Name);
  } else if(RCVPRN.equals("WHS_AUF")) {
  Name = DeliveryNumber + "_" + TimeStamp + ".S1B";
  message.setProperty("FileName1", Name);
println(Name);
  } else if(RCVPRN.equals("WHS_DUB")) {
  Name = "sadv";
  message.setProperty("FileName1", Name);
println(Name);
} else {
Name = "sadv";
  message.setProperty("FileName1", Name);
println(Name);
}
  return message;
}