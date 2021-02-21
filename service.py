import sys,codecs
from requests import get
from os import path
from json import loads, load
from shutil import rmtree
from time import time
from traceback import format_exc
from unicodedata import normalize
from urllib.parse import unquote_plus, unquote, quote, urlparse
from xbmcaddon import Addon
from xbmcplugin import endOfDirectory, addDirectoryItem
from xbmcgui import ListItem, Dialog
from xbmcvfs import listdir, exists, mkdirs, translatePath
from xbmc import executebuiltin, getInfoLabel, executeJSONRPC, Player, log, getCondVisibility


myAddon = Addon()
myScriptID = myAddon.getAddonInfo('id')
myVersion = myAddon.getAddonInfo('version')
myTmp = translatePath(myAddon.getAddonInfo('profile'))
mySubFolder = translatePath(path.join(myTmp, 'subs'))
myName = myAddon.getAddonInfo('name')
myLang = myAddon.getLocalizedString

def getDomain():
	try:
		myDomain = str(get('https://pastebin.com/raw/1vbRPSGh').text)
		return myDomain
	except Exception as err:
		wlog(f'Caught Exception: error in finding getDomain: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		return "lolfw.com"

myDomain = getDomain()

def convert_to_utf(file):
	try:
		with codecs.open(file, "r", "cp1255") as f:
			srt_data = f.read()

		with codecs.open(file, 'w', 'utf-8') as output:
			output.write(srt_data)
	except Exception as err:
		wlog(f'Caught Exception: error converting to utf: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		pass


def lowercase_with_underscores(str):
	return normalize('NFKD', str)


def download(id):
	try:
		rmtree(mySubFolder)
	except Exception as err:
		wlog(f'Caught Exception: error deleting folders: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		pass
	mkdirs(mySubFolder)
	subtitle_list = []
	exts = [".srt", ".sub", ".str"]
	archive_file = path.join(myTmp, 'wizdom.sub.'+id+'.zip')
	if not path.exists(archive_file):
		data = get(f"http://zip.{format(myDomain)}/"+id+".zip")
		open(archive_file, 'wb').write(data.content)
	executebuiltin(f'XBMC.Extract({archive_file},{mySubFolder})', True)
	for file_ in listdir(mySubFolder)[1]:
		ufile = file_.decode('utf-8')
		file_ = path.join(mySubFolder, ufile)
		if path.splitext(ufile)[1] in exts:
			convert_to_utf(file_)
			subtitle_list.append(file_)
	return subtitle_list

def getParams(arg):
	param = []
	paramstring = arg
	if len(paramstring) >= 2:
		params = arg
		cleanedparams = params.replace('?', '')
		if (params[len(params)-1] == '/'):
			params = params[0:len(params)-2]
		pairsofparams = cleanedparams.split('&')
		param = {}
		for i in range(len(pairsofparams)):
			splitparams = {}
			splitparams = pairsofparams[i].split('=')
			if (len(splitparams)) == 2:
				param[splitparams[0]] = splitparams[1]

	return param

def getParam(name, params):
	try:
		return unquote_plus(params[name])
	except Exception as err:
		wlog(f'Caught Exception: error getting param: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		pass

def searchByIMDB(imdb, season=0, episode=0, version=0):
	filename = f'wizdom.imdb.{imdb}.{season}.{episode}.json'
	url = f"http://json.{myDomain}/search.php?action=by_id&imdb={imdb}&season={season}&episode={episode}&version={version}"

	wlog(f"searchByIMDB: {url}")
	json = cachingJSON(filename,url)
	subs_rate = []  # TODO remove not in used
	if json != 0:
		for item_data in json:
			listitem = ListItem(label="Hebrew", label2=item_data["versioname"])
			listitem.setArt({ 'thumb': 'he', 'icon': str(item_data["score"]/2) })
			if int(item_data["score"]) > 8:
				listitem.setProperty("sync", "true")
			url = f'plugin://{myScriptID}/?action=download&versioname={item_data["versioname"]}&id={item_data["id"]}&imdb={imdb}&season={season}&episode={episode}'
			addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False)


def searchTMDB(type, query, year):
	tmdbKey = '653bb8af90162bd98fc7ee32bcbbfb3d'
	filename = f'wizdom.search.tmdb.{type}.{lowercase_with_underscores(query)}.{year}.json'
	if not year or year <= 0:
		url = f"http://api.tmdb.org/3/search/{type}?api_key={tmdbKey}&query={query}&language=en"
	else:
		url = f"http://api.tmdb.org/3/search/{type}?api_key={tmdbKey}&query={query}&year={year}&language=en"
		
	wlog(f"searchTMDB: {url}")
	json = cachingJSON(filename,url)
	try:
		if not json or not json["total_results"] or int(json["total_results"]) == 0:
			wlog(f'Got no results from TMDB')
			return 0
		tmdb_id = int(json["results"][0]["id"])
	except Exception as err:
		wlog(f'Caught Exception: error searchTMDB: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		return 0

	filename = f'wizdom.tmdb.{tmdb_id}.json'
	url = f"http://api.tmdb.org/3/{type}/{tmdb_id}/external_ids?api_key={tmdbKey}&language=en"
	response = get(url)
	json = loads(response.text)
	try:
		imdb_id = json["imdb_id"]
	except Exception:
		wlog(f'Caught Exception: error searching movie: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		return 0

	return imdb_id


def cachingJSON(filename, url):
	json_file = path.join(myTmp, filename)
	if not path.exists(json_file) or not path.getsize(json_file) > 20 or (time()-path.getmtime(json_file) > 30*60):
		data = get(url)
		wlog(f'HTTP GET: {url} \n Response: {data.content}')
		open(json_file, 'wb').write(data.content)
	if path.exists(json_file) and path.getsize(json_file) > 20:
		wlog(f'File [{filename}] already cached')
		with open(json_file,'r') as json_data:
			json_object = load(json_data)
		return json_object
	else:
		return 0


def ManualSearch(title):
	filename = f"wizdom.manual.{lowercase_with_underscores(title)}.json"
	url = f"http://json.{myDomain}/search.php?action=guessit&filename={lowercase_with_underscores(title)}"
	wlog(f"ManualSearch: {url}")
	try:
		json = cachingJSON(filename,url)
		if json["type"] == "episode":
			imdb_id = searchTMDB("tv",str(json['title']), 0)
			if imdb_id:
				searchByIMDB(str(imdb_id), 0, 0, lowercase_with_underscores(title))
		elif json["type"] == "movie":
			if "year" in json:
				imdb_id = searchTMDB("movie",str(json['title']), json['year'])
			else:
				imdb_id = searchTMDB("movie",str(json['title']), 0)
			if imdb_id:
				searchByIMDB(str(imdb_id), 0, 0, lowercase_with_underscores(title))
	except Exception as err:
		wlog(f'Caught Exception: error in manual search: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		pass


def wlog(msg, level=xbmc.LOGDEBUG):
	log(f"##**## [Wizdom Subs] {msg}", level=level)


# ---- main -----
if not exists(myTmp):
	mkdirs(myTmp)

action = None
if len(sys.argv) >= 2:
	params = getParams(sys.argv[2])
	action = getParam("action", params)

wlog(f"Version: {myVersion}")
wlog(f"Action: {action}")

if action == 'search':
	item = {}

	wlog(f"isPlaying: {Player().isPlaying()}")
	if Player().isPlaying():
		item['year'] = getInfoLabel("VideoPlayer.Year")  # Year

		item['season'] = str(getInfoLabel("VideoPlayer.Season"))  # Season
		if item['season'] == '' or item['season'] < 1:
			item['season'] = 0
		item['episode'] = str(getInfoLabel("VideoPlayer.Episode"))  # Episode
		if item['episode'] == '' or item['episode'] < 1:
			item['episode'] = 0

		if item['episode'] == 0:
			item['title'] = lowercase_with_underscores(getInfoLabel("VideoPlayer.Title"))  # no original title, get just Title
		else:
			item['title'] = lowercase_with_underscores(getInfoLabel("VideoPlayer.TVshowtitle"))  # Show
		if item['title'] == "":
			item['title'] = lowercase_with_underscores(getInfoLabel("VideoPlayer.OriginalTitle"))  # try to get original title
		item['file_original_path'] = unquote(Player().getPlayingFile())  # Full path of a playing file
		item['file_original_path'] = item['file_original_path'].split("?")
		item['file_original_path'] = path.basename(item['file_original_path'][0])[:-4]
		
	else:   # Take item params from window when kodi is not playing
		labelIMDB = getInfoLabel("ListItem.IMDBNumber")
		item['year'] = getInfoLabel("ListItem.Year")
		item['season'] = getInfoLabel("ListItem.Season")
		item['episode'] = getInfoLabel("ListItem.Episode")
		item['file_original_path'] = ""
		labelType = getInfoLabel("ListItem.DBTYPE")  # movie/tvshow/season/episode
		isItMovie = labelType == 'movie' or getCondVisibility("Container.Content(movies)")
		isItEpisode = labelType == 'episode' or getCondVisibility("Container.Content(episodes)")

		if isItMovie:
			item['title'] = getInfoLabel("ListItem.OriginalTitle")
		elif isItEpisode:
			item['title'] = getInfoLabel("ListItem.TVShowTitle")
		else:
			item['title'] = "SearchFor..."  # In order to show "No Subtitles Found" result.
	
	wlog(f"item: {item}")
	imdb_id = 0
	try:
		if Player().isPlaying():	# Enable using subtitles search dialog when kodi is not playing
			playerid_query = '{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
			playerid = loads(executeJSONRPC(playerid_query))['result'][0]['playerid']
			imdb_id_query = '{"jsonrpc": "2.0", "method": "Player.GetItem", "params": {"playerid": ' + \
				str(playerid) + ', "properties": ["imdbnumber"]}, "id": 1}'
			imdb_id = loads(executeJSONRPC(imdb_id_query))['result']['item']['imdbnumber']
			wlog(f"imdb JSONPC: {imdb_id}")
		else:
			if labelIMDB:
				imdb_id = labelIMDB
			else:
				if isItMovie:
					imdb_id = "ThisIsMovie"  # Search the movie by item['title'] for imdb_id
				elif isItEpisode:
					imdb_id = "ThisIsEpisode"  # Search by item['title'] for tvdb_id
				else:
					imdb_id = "tt0"  # In order to show "No Subtitles Found" result => Doesn't recognize movie/episode
	except Exception as err:
		wlog(f"Caught Exception: error in imdb id: {format(err)}", xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)	
		pass

	if isinstance(imdb_id, str) and imdb_id[:2] == "tt":  # Simple IMDB_ID
		searchByIMDB(imdb_id, item['season'], item['episode'], item['file_original_path'])
	else:
		# Search TV Show by Title
		if item['season'] or item['episode']:
			try:
				imdb_id = searchTMDB("tv",quote(item['title']),0)
				wlog(f"Search TV TMDB:{imdb_id} [{item['title']}]")
				if isinstance(imdb_id, str) and imdb_id[:2] == "tt":
					searchByIMDB(imdb_id, item['season'], item['episode'], item['file_original_path'])
			except Exception as err:
				wlog(f'Caught Exception: error in tv search: {format(err)}', xbmc.LOGERROR)
				wlog(format_exc(), xbmc.LOGERROR)
				pass
		# Search Movie by Title+Year
		else:
			try:
				imdb_id = searchTMDB("movie",query=item['title'], year=item['year'])
				wlog(f"Search TMDB:{imdb_id}")
				if not isinstance(imdb_id, str) or not imdb_id[:2] == "tt":
					imdb_id = searchTMDB("movie",query=item['title'], year=(int(item['year'])-1))
					wlog(f"Search IMDB(2):{imdb_id}")
				if isinstance(imdb_id, str) and imdb_id[:2] == "tt":
					searchByIMDB(imdb_id, 0, 0, item['file_original_path'])
			except Exception as err:
				wlog(f'Caught Exception: error in movie search: {format(err)}', xbmc.LOGERROR)
				wlog(format_exc(), xbmc.LOGERROR)
				pass

	# Search Local File
	if not imdb_id:
		ManualSearch(item['title'])
	endOfDirectory(int(sys.argv[1]))
	if myAddon.getSetting("Debug") == "true":
		if isinstance(imdb_id, str) and imdb_id[:2] == "tt":
			Dialog().ok(str(item), "imdb: "+str(imdb_id))
		else:
			Dialog().ok(str(item), "NO IDS")

elif action == 'manualsearch':
	searchstring = getParam("searchstring", params)
	ManualSearch(searchstring)
	endOfDirectory(int(sys.argv[1]))

elif action == 'download':
	id = getParam("id", params)
	wlog(f"Download ID: {id}")
	subs = download(id)
	for sub in subs:
		listitem = ListItem(label=sub)
		addDirectoryItem(handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False)
	endOfDirectory(int(sys.argv[1]))
	Ap = 0

	# Upload AP
	try:
		if urlparse(Player().getPlayingFile()).hostname[-11:]=="tv4.live":
			Ap = 1
	except:
		pass
	
	if Ap==1 and myAddon.getSetting("uploadAP") == "true":
		try:
			response = get(f'http://subs.vpnmate.com/webupload.php?status=1&imdb={getParam("imdb", params)}&season={getParam("season", params)}&episode={getParam("episode", params)}')
			ap_object = loads(response.text)["result"]
			if ap_object["lang"]["he"]==0:
				xbmc.sleep(30*1000)
				i = Dialog().yesno("Apollo Upload Subtitle" ,f"Media version {ap_object['version']}","This subtitle is 100% sync and match?")
				if i == 1:
					response = get(f'http://subs.vpnmate.com/webupload.php?upload=1&lang=he&subid={getParam("id", params)}&imdb={getParam("imdb", params)}&season={getParam("season", params)}&episode={getParam("episode", params)}')
					ap_upload = loads(response.text)["result"]
					if "error" in ap_upload:
						Dialog().ok("Apollo Error",f'{ ap_upload["error"] }')
					else:
						Dialog().ok("Apollo","Sub uploaded. Thank you!")
		except:
			pass

elif action == 'clean':
	try:
		rmtree(myTmp)
	except Exception as err:
		wlog(f'Caught Exception: deleting tmp dir: {format(err)}', xbmc.LOGERROR)
		wlog(format_exc(), xbmc.LOGERROR)
		pass
	executebuiltin(f'Notification({myName},{myLang(32004)}')
