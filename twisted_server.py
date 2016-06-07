# -*- coding: UTF-8 -*-

import os
import subprocess
import hashlib
import threading
import random
import time
import re

if os.name!='nt':
    from twisted.internet import epollreactor
    epollreactor.install()    
else:
    from twisted.internet import iocpreactor
    iocpreactor.install()

from base64 import b64encode, b64decode
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet import defer

g_code_length = 0
g_header_length = 0
nick = 1

class Chat(LineReceiver):

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, users, father):
        self.users = users
        self.name = None
        self.path = "/"
        self.state = "NOT_LOGIN"
        self.client_connect_type = 'None'
        self.client_ip = '0.0.0.0'
        self.client_port = '0'
        self.buffer = ""
        self.buffer_utf8 = ""
        self.length_buffer = 0
        self.nickname = ""
        self.lastnickname = ""
        self.serverstate = "AL_TALK"
        self.fatheradd = father
        self.game = ""
        self.add = self

    def connectionMade(self):
        try:
            self.transport.setTcpKeepAlive(1)
        except:
            self.connectionLost("TimeOut")
        self.__initClientInfo()
        self.__initServerInfo()

    def connectionLost(self, reason):
        print 'Client Disconnected:', self.client_ip + ':' + self.client_port
        if self.users.has_key(self.name):
            del self.users[self.name]

    def lineReceived(self, line):
        pass

    def dataReceived(self, data):
        global nick
        global g_code_length
        global g_header_length  

        headers = {}
        if self.state == "NOT_LOGIN":

            self.name = nick
            self.users[nick] = self
            nick = nick + 1

            if data.find('\r\n\r\n') != -1:
                header, data = data.split('\r\n\r\n', 1)

                for line in header.split("\r\n")[1:]:
                    key, value = line.split(": ", 1)
                    headers[key] = value

                headers["Location"] = ("ws://%s%s" %(headers["Host"], self.path))
                key = headers['Sec-WebSocket-Key']
                token = b64encode(hashlib.sha1(str.encode(str(key + self.GUID))).digest())

                handshake="HTTP/1.1 101 Switching Protocols\r\n"\
                    "Upgrade: websocket\r\n"\
                    "Connection: Upgrade\r\n"\
                    "Sec-WebSocket-Accept: "+bytes.decode(token)+"\r\n"\
                    "WebSocket-Origin: "+str(headers["Origin"])+"\r\n"\
                    "WebSocket-Location: "+str(headers["Location"])+"\r\n\r\n"

                self.nickname = self.client_ip
                self.lastnickname = self.client_ip
                self.transport.write(str.encode(str(handshake)))
                self.publicchat("Welcome to " + self.nickname + "!")
                self.state = "LOGIN"

                print "Socket %s connect sucess." % (self.name)

        else:
            self.length_buffer = self.length_buffer + len(data)
            self.buffer = self.buffer + data
            self.buffer_utf8 = self.parse_data(self.buffer)          
            msg_unicode = str(self.buffer_utf8).decode('utf-8', 'ignore')
            if msg_unicode=='quit':
                self.publicchat("%s leave." % (self.nickname))
                self.connectionLost("Quit")
            else:
                if self.serverstate == "AL_TALK" :
                    try:
                        tempnickname, msg_unicode = msg_unicode.split('&')
                        if tempnickname != self.lastnickname and tempnickname != "Null":
                            self.nickname = tempnickname
                            self.publicchat("%s change nickname to %s." % (self.lastnickname, self.nickname))
                            self.lastnickname = self.nickname
                    except:
                        self.connectionLost("Error NickName.");
                    if len(msg_unicode) > 0 :
                        if msg_unicode[0] == "@" :
                            try:
                                to, msg_unicode = msg_unicode.split(" ")
                                self.privatechat(to[1:], "%s side-text to %s : %s" % (self.nickname, to[1:], msg_unicode))
                            except:
                                print "Side-text error."
                        elif msg_unicode == "Who is caunch":
                            self.fatheradd.whosyourdaddy.start(self.users[self.name])
                        elif msg_unicode == "join" and self.fatheradd.whosyourdaddy.state == "ENLIST" :
                            self.game = self.fatheradd.whosyourdaddy.enlist(self.users[self.name])
                        else:
                            self.publicchat("%s say : %s" % (self.nickname, msg_unicode))
                else:
                    if self.game.talktest(self.users[self.name]):
                        tempnickname, msg_unicode = msg_unicode.split('&')
                        self.gamechat("%s say : %s" % (self.nickname, msg_unicode))
            self.buffer_utf8 = ""
            self.buffer = ""
            g_code_length = 0
            self.length_buffer = 0
        self.buffer = ""

    def publicchat(self, message):
        for id in self.users.keys():
            if self.users[id].serverstate == "AL_TALK":
                try:
                    self.users[id].transport.write(self.translate(message))
                except:
                    self.publicchat("%s exit." % (self.users[id].nickname))
                    print 'Found dead socket.'
                    del self.users[id]

    def gamechat(self, message):
        tempadd = self.game.getplayer()
        for id in tempadd.keys():
            #try:
            self.game.vote(self.name, message)
            tempadd[id].transport.write(self.translate(message))
            #except:
            #    print "Error"

    def privatechat(self, id, message):
        for tempname in self.users.keys():
            if self.users[tempname].nickname == id or self.users[tempname].add == id :
                try:
                    self.users[tempname].transport.write(self.translate(message))
                    #self.transport.write(self.translate(message))
                    break
                except:
                    self.transport.write(self.translate("Side-text user was leave."))
                    print "Private user is dead."
                    del self.users[id]

        else:
            self.transport.write(self.translate("Side-text user not exist."))

    def translate(self, message):

        message_utf_8 = message.encode('utf-8')
        back_str = []
        back_str.append('\x81')
        data_length = len(message_utf_8)

        if data_length <= 125:
            back_str.append(chr(data_length))
        elif data_length <= 65535 :
            back_str.append(struct.pack('b', 126))
            back_str.append(struct.pack('>h', data_length))
        elif data_length <= (2^64-1):
            back_str.append(struct.pack('b', 127))
            back_str.append(struct.pack('>q', data_length))
        else :
            print (u'too long')     
        msg = ''
        for c in back_str:
            msg += c;
        back_str = str(msg) + message_utf_8
        if back_str != None and len(back_str) > 0:
            #print (unicode(back_str[2:], "utf-8"))
            return back_str

    def parse_data(self, msg):
        global g_code_length
        g_code_length = ord(msg[1]) & 127
        received_length = 0;
        if g_code_length == 126:
            g_code_length = struct.unpack('>H', str(msg[2:4]))[0]
            masks = msg[4:8]
            data = msg[8:]
        elif g_code_length == 127:
            g_code_length = struct.unpack('>Q', str(msg[2:10]))[0]
            masks = msg[10:14]
            data = msg[14:]
        else:
            masks = msg[2:6]
            data = msg[6:]
        i = 0
        raw_str = ''
        for d in data:
            raw_str += chr(ord(d) ^ ord(masks[i%4]))
            i += 1
        return raw_str

    def __initClientInfo(self):
        str_client_info = str(self.transport.getPeer())
        self.client_connect_type = str_client_info.split('(')[1].split(',')[0].strip()
        self.client_ip = str_client_info.split("'")[1].strip()
        self.client_port = str_client_info.split(",")[2].strip()[:-1]
        print 'Client Connected:', self.client_ip + ':' + self.client_port, 'via', self.client_connect_type

    def __initServerInfo(self):
        str_client_info = str(self.transport.getHost())
        self.server_connect_type = str_client_info.split('(')[1].split(',')[0].strip()
        self.server_ip = str_client_info.split("'")[1].strip()
        self.server_port = str_client_info.split(",")[2].strip()[:-1]

class WhosyourDaddy(object):

    playerid = 1

    def __init__(self):
        self.state = "NOT_ING"
        self.gamemaster = ""
        self.player = {}
        self.uncaunch = {}
        self.caunch = {}
        self.voresult = {}
        self.hadvote = []
        self.allowtalk = "ALL"
        self.caunchnum = 0

    def start(self, masterid):
        self.gamemaster = masterid
        self.gamemaster.publicchat(u"Who is undercover game will start in 30 seconds,and you can enter the 'join' to join the game.")
        self.state = "ENLIST"
        threading.Timer(10.0, self.begin).start()

    def begin(self):
        if len(self.player) >= 2 :
            tempcaunch = random.randint(1,len(self.player))
            self.caunchnum = tempcaunch
            self.caunch[tempcaunch] = self.player[tempcaunch]
            for num in range(1,len(self.player)+1):
                if num != tempcaunch :
                    self.uncaunch[num] = self.player[num]
            for key in self.uncaunch.keys() :
                self.gamemaster.privatechat(self.uncaunch[key], u"Your identity is not undercover.")
                self.uncaunch[key].serverstate = "UNAL_TALK"
            for key in self.caunch.keys() :
                self.gamemaster.privatechat(self.caunch[key], u"Your identity is undercover.")
                self.caunch[key].serverstate = "UNAL_TALK"
            self.allzero()
            self.talk()

        else:
            self.gamemaster.publicchat(u"Who is undercover game because the number of applicants is less than four so can not start.")
            self.state = "NOT_ING"

    def allzero(self):
        for key in self.player.keys():
            self.voresult[key] = 0

    def talk(self):
        for playboy in self.player.keys():
            self.gamemaster.gamechat(u"Next is the number %s player to speak." % (str(playboy)))
            self.gamemaster.privatechat(self.player[playboy], u"Your will have 20 seconds to talk.")
            #threading.Timer(20.0, self.talkover).start()
            self.allowtalk = self.player[playboy]
            time.sleep(20)
            self.gamemaster.privatechat(self.player[playboy], u"Your self time is over.")
        self.votetime()

    def talktest(self, add):
        if add == self.allowtalk or self.allowtalk == "ALL" :
            return True
        else:
            return False

    def votetime(self):
        self.gamemaster.gamechat(u"The next 20 seconds is the voting time, you can enter the number + serial number of votes, such as: number 5.")
        self.allowtalk = "ALL"
        self.state = "VOTING"
        threading.Timer(20.0, self.voteover).start()

    def vote(self, id, message):
        if self.state == "VOTING":
            if id not in self.hadvote :
                tenick, temessage = message.split(":")
                temessage = temessage[1:]
                try:
                    who = re.match("^number +[0-9]{1,2}$",temessage).group().split()[-1]
                #id.privatechat(id.nickname, "You vote to %s." % (int(who)))
                #for i in self.voresult.keys():
                #    print i, self.voresult[i]
                    if self.voresult.has_key(int(who)):
                        self.voresult[int(who)] = self.voresult[int(who)] + 1
                        self.hadvote.append(id)
                except:
                    print "error"

    def voteover(self):
        self.state = "ING"
        self.gamemaster.gamechat(u"Voting time is over.")
        sort = sorted(self.voresult.items(), key=lambda e:e[0], reverse=False)
        self.allzero()
        self.kick(sort[0][0])

    def enlist(self, useradd):
        if self.state == "ENLIST":
            self.player[self.playerid] = useradd
            useradd.privatechat(useradd.nickname, "Enlist sucess! your id is %d." % (self.playerid))
            self.playerid = self.playerid + 1
            return self

    def getplayer(self):
        return self.player

    def kick(self, id):
        if self.caunchnum == id :
            self.gamemaster.gamechat(u"Game Over The caunch is number %s." % (str(id)))
            self.gameover()
        else:
            self.gamemaster.gamechat(u"%s is not the caunch." % (str(id)))
            del self.uncaunch[id]
            if len(self.uncaunch) < 2:
                self.gamemaster.gamechat(u"Game over the caunch is win!")
                self.gameover()
            else:
                self.gamemaster.gamechat(u"Start the next round!")
                self.talk()

    def gameover(self):
        for i in self.player.keys():
            self.player[i].serverstate = "AL_TALK"
        self.playerid = 1
        self.state = "NOT_ING"
        self.gamemaster = ""
        self.player = {}
        self.uncaunch = {}
        self.caunch = {}
        self.voresult = {}
        self.hadvote = []
        self.allowtalk = "ALL"
        self.caunchnum = 0

class ChatFactory(Factory):
    def __init__(self):
        self.users = {}
        self.whosyourdaddy = WhosyourDaddy()
        self.add = self

    def buildProtocol(self, addr):
        self.chat = Chat(self.users, self.add)
        return self.chat

if __name__ == '__main__':
    port = 1234
    reactor.listenTCP(port, ChatFactory())
    print 'Server started at 127.0.0.1:%d.' % port
    reactor.run()