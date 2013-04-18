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
SHOW_CHANNEL = "channel"
PARAMETER_KEY_MODE = "mode"
PARAMETER_KEY_PLAYPATH = "playpath"
PARAMETER_KEY_STATION = "station"
PARAMETER_KEY_CID = "cid"
PARAMETER_KEY_CID2 = "cid2"
PARAMETER_KEY_TITLE = "title"
PARAMETER_KEY_CHANNEL = "channel"
PARAMETER_KEY_NAME = "name"
PARAMETER_KEY_IMAGE = "image"

URL_BASE = "http://www.teamstream.to/"
EPG_URL = "http://www.hoerzu.de/tv-programm/jetzt/"
CACHE_FILE = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/cache.dat")
STREAMS_FILE = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/streams.xml")
LOGFILE =  xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/log.txt")
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
		xbmc.log("### %s" % msg, level=xbmc.LOGNOTICE)
	except:
		logf.write( "logging error")
	
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
	#log ( repr( cookie))
	log( "logging in...")
	login = settings.getSetting( id="login")
	password = settings.getSetting( id="password")
	url = URL_BASE + "login.php"
	args = {	"vb_login_username": login,
				"vb_login_password": password,
				"cookieuser": "1",
				"securitytoken:": "guest",
				"url": "/forum.php",
				"do": "login"}
	
	cookie = cookielib.Cookie(version=0, name='sitechrx', value='a84cdef5f86879be4509b67216281021', port=None, port_specified=False, domain='www.teamstream.to', domain_specified=False, domain_initial_dot=False, path='/', path_specified=True, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
	cookies.set_cookie(cookie)	
	reply = fetchHttp( url, args, post=True);
	if not "deine Anmeldung" in reply:
		log( "login failure")
		log( reply)
		notify( "Login Failure!", "Please set your login/password in the addon settings")
		xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=False)
		return False
	log( "login ok")
	return True
	
def get_channels():
	xml = etree.parse( STREAMS_FILE )
	channels = []
	for channel in xml.xpath("//channel"):
		chan = {	"name": channel.get("name"),
					"image": channel.get("image") }
		channels.append( chan )
		
	return channels
		
		
def get_channel_items(chan):
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

def get_image(image):
	image = IMG_PATH + image
	if os.path.exists(image):
		return image
	else:
		return ""
	
def get_streamparams(force=False):
	if os.path.exists(CACHE_FILE) and not force:
		params = pickle.load( open(CACHE_FILE, 'r') )
		return params

	if login():
		url = URL_BASE + get_link()
		html = fetchHttp(url, post=False)
		html = lxml.html.fromstring( html )
		
		streamcontainer = html.xpath("//div[@id='streamcontainer']")[0]
		#return lxml.html.tostring(streamcontainer)
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
		
		pickle.dump( params, open(CACHE_FILE, 'w') )				
		return params

def get_link(url=""):
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
					return get_link(URL_BASE + href)
				else:
					return href

def get_epg(channel, html):
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
				remaining = etime - stime
				if category != "":
					the_string = "{0} (noch {1}' | {2})".format(current_show.encode("utf-8"), str(remaining), category.encode("utf-8"))
				else:
					the_string = "{0} (noch {1}')".format(current_show.encode("utf-8"), str(remaining))
				the_string = the_string.decode("utf-8")
				return the_string
	except:
		return ""
	
###################
# Directory Stuff #
###################
def show_main():
	get_streamparams()
	for channel in get_channels():
		chan = channel["name"]
		img = get_image( channel["image"] )
		addDirectoryItem( chan, {PARAMETER_KEY_MODE: SHOW_CHANNEL, PARAMETER_KEY_CHANNEL: chan }, img, folder=True)

	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)

def show_channel(channel):

	channel = channel.replace("+", " ")

	req = urllib2.Request( EPG_URL )
	html = urllib2.urlopen(req).read()
	
	for item in get_channel_items(channel):
		name = item["title"]
		if item['epg'] is not None:
			epg = get_epg( item['epg'], html )
			if epg != "":
				title = name + " - " + epg
			else:
				title = name
		else:
			title = name
			
		playpath = item["playpath"]
		img = get_image ( item["image"] )
			
		addDirectoryItem( title, { PARAMETER_KEY_IMAGE: item["image"], PARAMETER_KEY_NAME: name, PARAMETER_KEY_PLAYPATH: playpath, PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_TITLE: title }, img)

	xbmcplugin.endOfDirectory( handle=pluginhandle, succeeded=True)
	
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
	ok = show_main()

elif mode == SHOW_CHANNEL:
	channel = params[PARAMETER_KEY_CHANNEL]
	show_channel(channel)

elif mode == MODE_PLAY:
	stream_params = get_streamparams()
	playpath = params[PARAMETER_KEY_PLAYPATH]
	url = "%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true live=true" % (stream_params["rtmp"], stream_params["flv"], stream_params["pageurl"], playpath)
	name = params[PARAMETER_KEY_TITLE].replace("+"," ")
	
	img = get_image ( params[PARAMETER_KEY_IMAGE] )
	
	li = xbmcgui.ListItem( name, iconImage=img, thumbnailImage=img)
	li.setProperty( "IsPlayable", "true")
	li.setProperty( "Video", "true")
	
	xbmc.Player().play(url, li)
	xbmc.sleep(500)
	if not xbmc.Player().isPlaying():
		notify("Stream Error", "Cleaning cache and retrying ...")
		stream_params = get_streamparams(force=True)
		url = "%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true live=true" % (stream_params["rtmp"], stream_params["flv"], stream_params["pageurl"], playpath)
		xbmc.Player().play(url, li)