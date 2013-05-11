import os, re, sys
import threading
import cookielib, urllib, urllib2, HTMLParser
from cookielib import CookieJar
import datetime
import xbmcgui, xbmcplugin, xbmcaddon
import os.path
import cPickle as pickle
import time
from BeautifulSoup import BeautifulSoup

__author__     = "siriuz"
__copyright__  = "Copyright 2013, teamstream.to"
__maintainer__ = "siriuz"
__email__      = "siriuz@gmx.net"

########################
# constants definition #
########################
PLUGINID = "plugin.video.teamstream"
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
	
	js_url = BeautifulSoup( html)
	js_url = js_url.find("script")['src']
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
	xml = BeautifulSoup( open(STREAMS_FILE,"r").read())
	channels = []
	for channel in xml.findAll("channel"):
		chan = {	"name": channel["name"],
					"image": channel["image"] }
		channels.append( chan )
		
	return channels
		
		
def getChannelItems(chan):
	items = []
	xml = BeautifulSoup( open(STREAMS_FILE,"r").read())
	for channel in xml.findAll("channel"):
		if channel["name"] == chan:
			for item in channel.findAll("item"):
				items.append( { "title": item.find("title").string,
								"epg": item.find("epg").string,
								"image": item.find("image").string,
								"playpath": item.find("file").string } )
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
			html = BeautifulSoup(html)
			
			streamcontainer = html.find("div", id="streamcontainer")
			flv = streamcontainer.find("embed")["src"]
			flashvars =streamcontainer.find("embed")["flashvars"]
			playlist = flashvars.split("file=")[1].split("&")[0]
			xml = fetchHttp(playlist, hdrs= { "Referer": url },  post=False)
			xml = BeautifulSoup(xml)
			rtmp = xml.find("jwplayer:streamer").string

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
	
	html = fetchHttp( url, post=False)
	html = BeautifulSoup( html)
	for link in html.findAll("a"):
		cmp = link.text
		if cmp == "TS Stream Box (SD+HD)":
			href=link["href"]
			if "newpost" not in href:
				if flag:
					return getLink(URL_BASE + href)
				else:
					return href

def getChannelListEPG():
	channel_list = []
	stime = (int(time.strftime("%H")) * 60) + (int(time.strftime("%M")))
	html = urllib2.urlopen("http://www.hoerzu.de/tv-programm/jetzt/")
	soup = BeautifulSoup(html)
	divs = soup.findAll("div", {"class":"block"})
	for div in divs:
		channels = div.findAll("ul", {"class":"tvshows"})
		for channel in channels:
			try:
				log("Scanning Channel")
				channel_name = channel.parent.findAll("div", {"class":"channel"})[0].string
				current_show =  channel.find("b", {"class":"title"}).string
				etime = channel.findAll("span", {"class":"starttime"})[1].string
				category = channel.find("span", {"class":"year-country"}).string
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
			except:
				the_string = ""
				
			channel_list.append({	"name":channel_name,
									"info":the_string})
	return channel_list
	
def getEPG(channel_name,channel_list):
	retval = ""
	for channel in channel_list:
		if channel_name == channel["name"]:
			retval = channel["info"]
	return retval
		
def getEventsPerDay(day, html):
	html = BeautifulSoup( html)
	div_id = "tab-%s" % day
	table = html.find("div", id=div_id)
	if table is not None:
		return getEventRows(table)
	else:
		return False
	
def getEventRows(table):
	ret_rows = []
	for row in table.findAll("tr"):
		name = str(row.findAll("td")[2])
		m = re.search('<td style="width:295px">(.*)<br />(.*)</td>', name)
		name = m.group(1) + ": " + m.group(2)
		url = URL_BASE + "plan/" + row.find("img")["src"]
		img = url.split("pics/")[1]
		downloadImage( url, img)
		ret_rows.append({ "img": img,
					"start_time": row.findAll("td")[1].string,
					"name": name,
					"station_id": row.findAll("td")[3].string })
		
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
			pass
			log( "Eventplaner Cache ist zu alt, erneuere ihn ...")
	
	else:
		pass
		log( "Eventplaner Cache nicht gefunden, erstelle ihn ...")
	
	if login():
		html = fetchHttp(url)		
		f = open(EVENTPLAN_CACHE, 'w')
		f.write(html)
		f.close()
		return html
		
def getPlayPath(station_id):
	retval = False
	xml = BeautifulSoup( open(STREAMS_FILE,"r").read())
	for item in xml.findAll("item"):
		try:
			if item["event_id"]  == station_id:
				retval = item.find("file").string
		except:
			pass
	return retval
	
###################
# Directory Stuff #
###################
def showMain():
	getStreamparams()
	for channel in getChannels():
		chan = channel["name"]
		img = getImage( channel["image"] )
		addDirectoryItem( chan, {"mode": "channel", "title": chan }, img, folder=True)
	
	addDirectoryItem("Eventplan", {"mode": "eventplan"}, image = getImage("eventplanner.png"), folder=True)
	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
	

def showChannel(channel):
	log ( "Entering showChannel(): " + channel)
	channel = channel.replace("+", " ")
	if settings.getSetting( id="epg") == "true":
		channel_list = getChannelListEPG()
	
	for item in getChannelItems(channel):
		name = item["title"]
		if item['epg'] is not None and settings.getSetting( id="epg") == "true":
			epg = getEPG( item['epg'], channel_list)
			if epg != "":
				title = name + " - " + epg
			else:
				title = name
		else:
			title = name
			
		playpath = item["playpath"]
		img = getImage ( item["image"])
			
		addDirectoryItem( title, { "image": item["image"], "name": name, "playpath": playpath, "mode": "play", "title": title }, img)

	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
def showEventplan():
	
	days = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
	for i in range(7):	
		offset = (datetime.datetime.today() + datetime.timedelta(days=i)).weekday()
		img = getImage( days[offset] + ".png")
		label = days[offset]
		addDirectoryItem(label, {"mode": "eventday", "day": str(offset+1)}, image=img, folder=True)
		
	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
	
def showEventDay(day):

	html = getEventPlan()

	try:
		html = html.split('<body bgcolor="transparent" leftmargin="0" topmargin="0" marginwidth="0" marginheight="0">')[1]	
	except:
		log( html)

	html = getEventPlan()
	events = getEventsPerDay(day, html)
	if events:
		for event in events:
			title = name = event["start_time"] + " - " + event["name"]
			img = getImage( event["img"])
			playpath = getPlayPath( event["station_id"] )
			
			if playpath:			
				addDirectoryItem( title, { "image":  event["img"], "name": name, "playpath": playpath, "mode": "play", "title": title }, img)
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
mode = params.get("mode", "0")

# depending on the mode, call the appropriate function to build the UI.
if not sys.argv[2]:
	# new start
	ok = showMain()

elif mode == "channel":
	log( "Mode: Channel")
	channel = params["title"]
	showChannel(channel)
	
elif mode == "eventplan":
	showEventplan()
	
elif mode == "eventday":
	day = params["day"]
	log( "Calling day: " + day)
	showEventDay(day)

elif mode == "play":
	stream_params = getStreamparams()
	playpath = params["playpath"]
	url = "%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true live=true" % (stream_params["rtmp"], stream_params["flv"], stream_params["pageurl"], playpath)
	name = params["title"].replace("+"," ")
	
	img = getImage( params["image"] )
	
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
