var socket;

function init(){
  var host = "ws://127.0.0.1:1234/";
  try{
    socket = new WebSocket(host);
    socket.onopen    = function(msg){ ; };
    socket.onmessage = function(msg){ log(msg.data); };
    socket.onclose   = function(msg){ log("与服务器断开连接。"); };
  }
  catch(ex){ log(ex); }
  $("msg").focus();
}

var text=""; 
function f() 
{ 
var div11=document.getElementById("log"); 
if(text!=div11.innerHTML) 
{ 
  text=div11.innerHTML; 
  div11.scrollTop=div11.scrollHeight; 
} 
setTimeout("f()",0); 
} 
 
function send(){
  var txt,msg,nick,name;
  txt = $("msg");
  nick = $("nick");
  msg = txt.value;
  name = nick.value;
  if(!name){ name = "Null"; }
  if(!msg){ alert("消息不能为空。"); return; }
  txt.value="";
  txt.focus();
  try{ socket.send(name + "&" + msg); } catch(ex){ log(ex); }
}
 
window.onbeforeunload=function(){
    try{ 
        socket.send('quit'); 
        socket.close();
        socket=null;
    }
    catch(ex){ 
        log(ex);
    }
};
 
function $(id){ return document.getElementById(id); }
function log(msg){ $("log").innerHTML+="<br>"+msg; }
function onkey(event){ if(event.keyCode==13){ send(); } }
