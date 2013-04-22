import os, re, sys
import threading
import cookielib, urllib, urllib2, HTMLParser
from cookielib import CookieJar
import datetime
import xbmcgui, xbmcplugin, xbmcaddon
import simplejson as json
import os.path
import pickle
import time

if platform.system() == "Windows":
	sys.modules['lxml'] = __import__('lxml_win')
else platform.system() == "Linux":
	sys.modules['lxml'] = __import__('lxml_linux')

import lxml
import lxml.html
from lxml import etree


__author__     = "siriuz"
__copyright__  = "Copyright 2013, teamstream.to"
__maintainer__ = "siriuz"
__email__      = "siriuz@gmx.net"

########################
# constants definition #
########################
PLUGINID = "plugin.video.teamstream-win32"
MODE_PLAY = "play"
SHOW_CHANNEL= "channel"
SHOW_EVENTPLAN = "eventplan"
SHOW_EVENTDAY = "eventday"
PARAMETER_KEY_MODE = "mode"
PARAMETER_KEY_PLAYPATH = "playpath"
PARAMETER_KEY_STATION = "station"
PARAMETER_KEY_CID = "cid"
PARAMETER_KEY_CID2 = "cid2"
PARAMETER_KEY_TITLE = "title"
PARAMETER_KEY_CHANNEL = "channel"
PARAMETER_KEY_NAME = "name"
PARAMETER_KEY_IMAGE = "image"
PARAMETER_KEY_DAY = "day"

URL_BASE = "http://www.teamstream.to/"
EPG_URL = "http://www.hoerzu.de/tv-programm/jetzt/"
STREAM_CACHE = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/cache/stream.cache")
EVENTPLAN_CACHE = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/cache/eventplan.cache")
STREAMS_FILE = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/streams.xml")
LOGFILE =  xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/teamstream.log")
IMG_PATH = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/images/")


pluginhandle = int(sys.argv[1])
settings = xbmcaddon.Addon( id=PLUGINID)

entitydict = { "E4": u"\xE4", "F6": u"\xF6", "FC": u"\xFC",
               "C4": u"\xE4", "D6": u"\xF6", "DC": u"\xDC",
               "2013": u"\u2013"}


##########
# HELPER #
##########			
def notify( title, message):
	xbmc.executebuiltin("XBMC.Notification("+title+","+message+")")			
		
def log( msg):
	logf = open( LOGFILE, "a")
	logf.write( "%s: " % datetime.datetime.now().strftime( "%Y-%m-%d %I:%M:%S"))
	try:
		#msg = msg.encode( "latin-1")
		logf.write( msg)
		xbmc.log("### teamstream.to: %s" % msg, level=xbmc.LOGNOTICE)
	except:
		logf.write( "Logging Fehler")
	
	logf.write( '\n')
	logf.close()
	logf.close()
	
	
def fetchHttp( url, args={}, hdrs={}, post=False):
	#log( "fetchHttp(%s): %s" % ("POST" if post else "GET", url))
	hdrs["User-Agent"] = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/26.0.1410.64 Safari/537.31"		
	if post:
		req = urllib2.Request( url, urllib.urlencode( args), hdrs)
	else:
		req = urllib2.Request( url, None, hdrs)
		
	response = urllib2.urlopen( req)
	text = response.read()
	responsetext = text
	response.close()
	
	return responsetext
	
def parameters_string_to_dict( parameters):
	''' Convert parameters encoded in a URL to a dict. '''
	paramDict = {}
	if parameters:
		paramPairs = parameters[1:].split("&")
		for paramsPair in paramPairs:
			paramSplits = paramsPair.split('=')
			if (len(paramSplits)) == 2:
				paramDict[paramSplits[0]] = urllib.unquote( paramSplits[1])
	return paramDict
	
def htmldecode( s):
    try:
        h = HTMLParser.HTMLParser()
        s = h.unescape( s)
        for k in entitydict.keys():
            s = s.replace( "&#x" + k + ";", entitydict[k])
    except UnicodeDecodeError:
        pass
        
    return s

#################
# SCRAPER STUFF #
#################
def login():
	cookies = cookielib.LWPCookieJar()
	opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cookies))
	urllib2.install_opener( opener)
	
	log( "Logging in ...")
	html = fetchHttp( URL_BASE )
	
	js_url = lxml.html.fromstring( html )
	js_url = js_url.xpath("//script")[0].get("src")
	js_url = URL_BASE + js_url
	js = fetchHttp( js_url, hdrs = { "Referer": "http://www.teamstream.to/" })
	m = re.search(".*\"(.*)\"\).*", js)
	hsh2 = m.group(1)
	m = re.search(".*scf\('(.*)'\+'(.*)',.*", html)
	hsh1 = m.group(1) + m.group(2)
	sitechrx = hsh1 + hsh2
	
	login = settings.getSetting( id="login")
	password = settings.getSetting( id="password")
	
	if (login == "" or password == ""):
		error = "Username und/oder Passwort nicht gesetzt"
		log( "Login fehlgeschlagen:: " + error)
		notify( "Login fehlgeschlagen!", "Fehler: " + error)
		xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=False)
		return False	
	
	url = URL_BASE + "login.php"
	args = {	"vb_login_username": login,
				"vb_login_password": password,
				"cookieuser": "1",
				"securitytoken:": "guest",
				"url": "/forum.php",
				"do": "login"}
	
	cookie = cookielib.Cookie(version=0, name='sitechrx', value=sitechrx, port=None, port_specified=False, domain='www.teamstream.to', domain_specified=False, domain_initial_dot=False, path='/', path_specified=True, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
	cookies.set_cookie(cookie)	
	reply = fetchHttp( url, args, post=True);
	
	if not "deine Anmeldung" in reply:
		if 'onload="scf(' in reply:
			error = "Cookie Fehler"
			log( "Login fehlgeschlagen: " + error)	
			log( "Vardump[js_url]: " + js_url)
			log( "Vardump[js]: " + js)
			log( "Vardump[sitechrx]: " + sitechrx)
			log( "Reply: " + reply)
		elif "Login failed" in reply:
			error = "Username / Password stimmen nicht ueberein"
			log( "Login fehlgeschlagen: " + error)
		else:
			error = "Unbekannter Fehler"
			log( "Login fehlgeschlagen: " + error)	
			log( "Antwort: " + reply)
	
		notify( "Login fehlgeschlagen!", "Fehler: " + error)
		xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=False)
		return False
	else:
		log( "Login ok")
		return True

def getChannels():
	xml = etree.parse( STREAMS_FILE )
	channels = []
	for channel in xml.xpath("//channel"):
		chan = {	"name": channel.get("name"),
					"image": channel.get("image") }
		channels.append( chan )
		
	return channels
		
		
def getChannelItems(chan):
	items = []
	xml = etree.parse( STREAMS_FILE )
	for channel in xml.xpath("//channel"):
		if channel.get("name") == chan:
			for item in channel.xpath("item"):
				items.append( { "title": item.xpath("title")[0].text,
								"epg": item.xpath("epg")[0].text,
								"image": item.xpath("image")[0].text,
								"playpath": item.xpath("file")[0].text } )
			return items

def getImage(image):
	image = IMG_PATH + image
	if os.path.exists(image):
		return image
	else:
		return ""
	
def getStreamparams(force=False):
	if os.path.exists(STREAM_CACHE) and not force:
		params = pickle.load( open(STREAM_CACHE, 'r') )
		return params
	else:
		if login():
			url = URL_BASE + getLink()
			html = fetchHttp(url, post=False)
			html = lxml.html.fromstring( html )
			
			streamcontainer = html.xpath("//div[@id='streamcontainer']")[0]
			flv = streamcontainer.xpath("embed")[0].get("src")
			flashvars = streamcontainer.xpath("embed")[0].get("flashvars")
			playlist = flashvars.split("file=")[1].split("&")[0]
			xml = fetchHttp(playlist, hdrs= { "Referer": url },  post=False)
			xml = etree.fromstring( xml )
			namespace = { "jwplayer":"http://developer.longtailvideo.com/" }
			rtmp = xml.xpath("//rss/channel/item/jwplayer:streamer", namespaces=namespace)[0].text
			
			params = {	"flv": flv,
						"rtmp": rtmp,
						"pageurl": url }
			
			pickle.dump( params, open(STREAM_CACHE, 'w') )				
			return params
		else:
			return False

def getLink(url=""):
	flag = False
	
	if url == "":
		url = URL_BASE + "forum.php"
		flag = True
	
	html = fetchHttp(url, post=False)
	html = lxml.html.fromstring(html)
	for link in html.xpath("//a"):
		cmp = link.text
		if cmp == "TS Stream Box (SD+HD)":
			href=link.get("href")
			if "newpost" not in href:
				if flag:
					return getLink(URL_BASE + href)
				else:
					return href

def getEPG(channel, html):
	stime = (int(time.strftime("%H")) * 60) + (int(time.strftime("%M")))
	try:
		html = lxml.html.fromstring( html )
		elements = html.xpath("//*[@id='program-list']/div/div/div/div/ul/li")
		for element in elements:
			cmp = element.xpath("div[@class='channel']")[0].text
			if channel == cmp.strip():
				current_show = element.xpath("ul/li[1]/div/a[1]/b")
				if len(current_show) != 0:
					current_show = current_show[0].text
				else:
					current_show = element.xpath("ul/li[1]/div/div[1]/b")[0].text
				category = element.xpath("ul/li[1]/div/a[3]/span")
				if len(category) != 0:
					category = category[0].text
				else:
					category = element.xpath("ul/li[1]/div/span[3]")
					if len(category) != 0:
						category = category[0].text
					else:
						category = ""
				etime = element.xpath("ul/li[2]/div/a[2]/span")
				if len(etime) != 0:
					etime = etime[0].text
				else:
					etime = element.xpath("ul/li[2]/div/span")[0].text
				category = re.sub(r'\s\b[A-Z]{3}.*', '', category).strip()
				hours = int(etime.split(":")[0])
				minutes = int(etime.split(":")[1])
				etime = hours*60 + minutes
				if etime > stime:
					remaining = etime - stime
				else:
					remaining = (etime + 24*60) - stime
				if category != "":
					the_string = "{0} (noch {1}' | {2})".format(current_show.encode("utf-8"), str(remaining), category.encode("utf-8"))
				else:
					the_string = "{0} (noch {1}')".format(current_show.encode("utf-8"), str(remaining))
				the_string = the_string.decode("utf-8")
				return the_string
	except:
		return ""
		
def getEventsPerDay(day, html):
	xpath = "//div[@id='tab-%s']/table" % day
	table = html.xpath(xpath)
	if len(table) != 0:
		return getEventRows(table[0])
	else:
		return False
	
def getEventRows(table):
	ret_rows = []
	for row in table.xpath("tr"):
		name = lxml.html.tostring(row.xpath("td[3]")[0])
		m = re.search('<td style="width:295px">(.*)<br>(.*)</td>', name)
		name = m.group(1) + ": " + m.group(2)
		url = URL_BASE + "plan/" + row.xpath("td[1]/img")[0].get("src")
		img = url.split("pics/")[1]
		downloadImage( url, img)
		ret_rows.append({ "img": img,
					"start_time": row.xpath("td[2]")[0].text,
					"name": name,
					"station_id": row.xpath("td[4]")[0].text })
		
	return ret_rows
	

def downloadImage(url, img):
	img = IMG_PATH + img
	if not os.path.exists(img):
		try:
			response = urllib2.urlopen(url)
		except:
			log( "Bilddownload fehlgeschlagen: " + img)	
			return

		the_page = response.read()
		f = open(img, 'wb')
		f.write(the_page)
		f.close()
		
def getEventPlan():
	
	url = URL_BASE + "plan/index.php"
	write = False
	
	if os.path.exists(EVENTPLAN_CACHE):
		fileAge = time.time() - os.path.getmtime(EVENTPLAN_CACHE)
		if fileAge < 12*60*60:
			log( "Loading eventplan from cache ...")
			html = open(EVENTPLAN_CACHE, 'r').read()
			return html
		else:
			log( "Eventplaner Cache ist zu alt, erneuere ihn ...")
	
	else:
		log( "Eventplaner Cache nicht gefunden, erstelle ihn ...")
	
	if login():
		html = fetchHttp(url)		
		f = open(EVENTPLAN_CACHE, 'w')
		f.write(html)
		f.close()
		return html
		
def getPlayPath(station_id):
	xml = etree.parse( STREAMS_FILE )
	for item in xml.xpath("//item"):
		event_id = item.get("event_id")
		if event_id is not None and event_id == station_id:
			return item.xpath("file")[0].text
	
	return False
	
###################
# Directory Stuff #
###################
def showMain():
	getStreamparams()
	for channel in getChannels():
		chan = channel["name"]
		img = getImage( channel["image"] )
		addDirectoryItem( chan, {PARAMETER_KEY_MODE: SHOW_CHANNEL, PARAMETER_KEY_CHANNEL: chan }, img, folder=True)
	
	addDirectoryItem("Eventplan", {PARAMETER_KEY_MODE: SHOW_EVENTPLAN}, image = getImage("eventplanner.png"), folder=True)
	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
	

def showChannel(channel):

	channel = channel.replace("+", " ")
	req = urllib2.Request( EPG_URL )
	html = urllib2.urlopen(req).read()
		
	
	for item in getChannelItems(channel):
		name = item["title"]
		if item['epg'] is not 	None:
			epg = getEPG( item['epg'], html )
			if epg != "":
				title = name + " - " + epg
			else:
				title = name
		else:
			title = name
			
		playpath = item["playpath"]
		img = getImage ( item["image"])
			
		addDirectoryItem( title, { PARAMETER_KEY_IMAGE: item["image"], PARAMETER_KEY_NAME: name, PARAMETER_KEY_PLAYPATH: playpath, PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_TITLE: title }, img)

	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
def showEventplan():
	
	days = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
	for i in range(7):	
		offset = (datetime.datetime.today() + datetime.timedelta(days=i)).weekday()
		img = getImage( days[offset] + ".png")
		label = days[offset]
		addDirectoryItem(label, {PARAMETER_KEY_MODE: SHOW_EVENTDAY, PARAMETER_KEY_DAY: str(offset+1)}, image=img, folder=True)
		
	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
	
def showEventDay(day):

	html = getEventPlan()

	try:
		html = html.split('<body bgcolor="transparent" leftmargin="0" topmargin="0" marginwidth="0" marginheight="0">')[1]	
	except:
		log( html)

	html = lxml.html.fromstring( html )
	events = getEventsPerDay(day, html)
	if events:
		for event in events:
			title = name = event["start_time"] + " - " + event["name"]
			img = getImage( event["img"])
			playpath = getPlayPath( event["station_id"] )
			
			if playpath:			
				addDirectoryItem( title, { PARAMETER_KEY_IMAGE:  event["img"], PARAMETER_KEY_NAME: name, PARAMETER_KEY_PLAYPATH: playpath, PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_TITLE: title }, img)
			else:
				log( "Dieser Kanel kann noch nicht abgespielt werden: " + event["station_id"])
				img = IMG_PATH + "error.png"
				addDirectoryItem( title, image=img, folder=True)

		xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
	else:
		error = "Noch keine Daten fuer diesen Tag vorhanden"
		log ( error)
		notify("Eventplaner Fehler:", error)
			
def addDirectoryItem( name, params={}, image="", total=0, folder=False):
	'''Add a list item to the XBMC UI.'''
	img = "DefaultVideo.png"
	if image != "": img = image

	name = htmldecode( name)
	li = xbmcgui.ListItem( name, iconImage=img, thumbnailImage=image)         
	li.setProperty( "Video", "true")
    
	params_encoded = dict()
	for k in params.keys():
		params_encoded[k] = params[k].encode( "utf-8")
	url = sys.argv[0] + '?' + urllib.urlencode( params_encoded)
    
	return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=li, isFolder = folder, totalItems=total)
	
####################
# xbmc entry point #
####################
params = parameters_string_to_dict(sys.argv[2])
mode = params.get(PARAMETER_KEY_MODE, "0")

# depending on the mode, call the appropriate function to build the UI.
if not sys.argv[2]:
	# new start
	ok = showMain()

elif mode == SHOW_CHANNEL:
	channel = params[PARAMETER_KEY_CHANNEL]
	showChannel(channel)
	
elif mode == SHOW_EVENTPLAN:
	showEventplan()
	
elif mode == SHOW_EVENTDAY:
	day = params[PARAMETER_KEY_DAY]
	log( "Calling day: " + day)
	showEventDay(day)

elif mode == MODE_PLAY:
	stream_params = getStreamparams()
	playpath = params[PARAMETER_KEY_PLAYPATH]
	url = "%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true live=true" % (stream_params["rtmp"], stream_params["flv"], stream_params["pageurl"], playpath)
	name = params[PARAMETER_KEY_TITLE].replace("+"," ")
	
	img = getImage( params[PARAMETER_KEY_IMAGE] )
	
	li = xbmcgui.ListItem( name, iconImage=img, thumbnailImage=img)
	li.setProperty( "IsPlayable", "true")
	li.setProperty( "Video", "true")
	
	xbmc.Player().play(url, li)
	xbmc.sleep(1000)
	if not xbmc.Player().isPlaying():
		notify("Stream Fehler", "Cache wird erneuert ...")
		stream_params = getStreamparams(force=True)
		url = "%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true live=true" % (stream_params["rtmp"], stream_params["flv"], stream_params["pageurl"], playpath)
		xbmc.Player().play(url, li)
