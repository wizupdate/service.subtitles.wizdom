import os
import sys
import shutil
import urllib.request
import xbmc
import xbmcaddon
import xbmcplugin
import xbmcvfs
from json import loads, load
from time import time
from traceback import format_exc
from urllib.parse import unquote, quote
from xbmcgui import ListItem, Dialog

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo("author")
__scriptid__ = __addon__.getAddonInfo("id")
__scriptname__ = __addon__.getAddonInfo("name")
__version__ = __addon__.getAddonInfo("version")
__language__ = __addon__.getLocalizedString

__cwd__ = xbmcvfs.translatePath(__addon__.getAddonInfo("path"))
__profile__ = xbmcvfs.translatePath(__addon__.getAddonInfo("profile"))
__tmpfolder__ = xbmcvfs.translatePath(os.path.join(__profile__, "subs", ""))

if xbmcvfs.exists(__tmpfolder__):
    shutil.rmtree(__tmpfolder__)
xbmcvfs.mkdirs(__tmpfolder__)

from resources.lib.WizdomUtilities import (
    getParam,
    log,
    getDomain,
    normalizeString,
    cleanFolders,
    uploadAP,
)

myDomain = getDomain()


def download(id):
    cleanFolders(__tmpfolder__)
    subtitle_list = []
    exts = [".srt", ".sub", ".str"]
    archive_file = os.path.join(__tmpfolder__, "wizdom.sub." + id + ".zip")
    if not os.path.exists(archive_file):
        url = f"http://zip.{format(myDomain)}/" + id + ".zip"
        f = urllib.request.urlopen(url)
        with open(archive_file, "wb") as subFile:
            subFile.write(f.read())
        xbmc.sleep(500)

    xbmc.executebuiltin(
        (f"Extract({archive_file},{__tmpfolder__})").encode("utf-8"), True
    )
    for file in xbmcvfs.listdir(archive_file)[1]:
        file = os.path.join(__tmpfolder__, file)
        if os.path.splitext(file)[1] in exts:
            subtitle_list.append(file)

    return subtitle_list


def searchByIMDB(imdb, season=0, episode=0, version=0):
    filename = f"wizdom.imdb.{imdb}.{season}.{episode}.json"
    url = f"http://json.{myDomain}/search.php?action=by_id&imdb={imdb}&season={season}&episode={episode}&version={version}"

    log(f"searchByIMDB: {url}")
    json = cachingJSON(filename, url)
    subs_rate = []  # TODO remove not in used
    if json != 0:
        for item_data in json:
            listitem = ListItem(label="Hebrew", label2=item_data["versioname"])
            listitem.setArt({"thumb": "he", "icon": str(item_data["score"] / 2)})
            if int(item_data["score"]) > 8:
                listitem.setProperty("sync", "true")
            url = f'plugin://{__scriptid__}/?action=download&versioname={item_data["versioname"]}&id={item_data["id"]}&imdb={imdb}&season={season}&episode={episode}'
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False
            )


def searchTMDB(type, query, year):
    tmdbKey = "653bb8af90162bd98fc7ee32bcbbfb3d"
    filename = f"wizdom.search.tmdb.{type}.{normalizeString(query)}.{year}.json"
    if not year or year <= 0:
        url = f"http://api.tmdb.org/3/search/{type}?api_key={tmdbKey}&query={query}&language=en"
    else:
        url = f"http://api.tmdb.org/3/search/{type}?api_key={tmdbKey}&query={query}&year={year}&language=en"

    log(f"searchTMDB: {url}")
    json = cachingJSON(filename, url)
    try:
        if not json or not json["total_results"] or int(json["total_results"]) == 0:
            log(f"Got no results from TMDB")
            return 0
        tmdb_id = int(json["results"][0]["id"])
    except Exception as err:
        log(f"Caught Exception: error searchTMDB: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        return 0

    filename = f"wizdom.tmdb.{tmdb_id}.json"
    url = f"http://api.tmdb.org/3/{type}/{tmdb_id}/external_ids?api_key={tmdbKey}&language=en"
    req = urllib.request.urlopen(url)
    json = loads(req.read())
    try:
        imdb_id = json["imdb_id"]
    except Exception:
        log(f"Caught Exception: error searching movie: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        return 0

    return imdb_id


def cachingJSON(filename, url):
    json_file = os.path.join(__profile__, filename)
    if (
        not os.path.exists(json_file)
        or not os.path.getsize(json_file) > 20
        or (time() - os.path.getmtime(json_file) > 30 * 60)
    ):
        f = urllib.request.urlopen(url)
        content = f.read()
        log(f"HTTP GET: {url} \n Content: {content}")
        with open(json_file, "wb") as subFile:
            subFile.write(content)

    if os.path.exists(json_file) and os.path.getsize(json_file) > 20:
        log(f"File [{filename}] already cached")
        with open(json_file, "r") as json_data:
            json_object = load(json_data)
        return json_object
    else:
        return 0


def ManualSearch(title):
    filename = f"wizdom.manual.{normalizeString(title)}.json"
    url = f"http://json.{myDomain}/search.php?action=guessit&filename={normalizeString(title)}"
    log(f"ManualSearch: {url}")
    try:
        json = cachingJSON(filename, url)
        if json["type"] == "episode":
            imdb_id = searchTMDB("tv", str(json["title"]), 0)
            if imdb_id:
                searchByIMDB(str(imdb_id), 0, 0, normalizeString(title))
        elif json["type"] == "movie":
            if "year" in json:
                imdb_id = searchTMDB("movie", str(json["title"]), json["year"])
            else:
                imdb_id = searchTMDB("movie", str(json["title"]), 0)
            if imdb_id:
                searchByIMDB(str(imdb_id), 0, 0, normalizeString(title))
    except Exception as err:
        log(f"Caught Exception: error in manual search: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        pass


# ---- main -----
def get_params(string=""):
    param = []
    if string == "":
        paramstring = sys.argv[2]
    else:
        paramstring = string
    if len(paramstring) >= 2:
        params = paramstring
        cleanedparams = params.replace("?", "")
        if params[len(params) - 1] == "/":
            params = params[0 : len(params) - 2]
        pairsofparams = cleanedparams.split("&")
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split("=")
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    return param


if not xbmcvfs.exists(__profile__):
    xbmcvfs.mkdirs(__profile__)

action = None

params = get_params()
action = getParam("action", params)

log(f"Version: {__version__}")
log(f"Action: {action}")

if action == "search":
    item = {}

    log(f"isPlaying: {xbmc.Player().isPlaying()}")
    if xbmc.Player().isPlaying():
        item["year"] = xbmc.getInfoLabel("VideoPlayer.Year")  # Year

        item["season"] = str(xbmc.getInfoLabel("VideoPlayer.Season"))  # Season
        if item["season"] == "" or item["season"] < 1:
            item["season"] = 0
        item["episode"] = str(xbmc.getInfoLabel("VideoPlayer.Episode"))  # Episode
        if item["episode"] == "" or item["episode"] < 1:
            item["episode"] = 0

        if item["episode"] == 0:
            item["title"] = normalizeString(
                xbmc.getInfoLabel("VideoPlayer.Title")
            )  # no original title, get just Title
        else:
            item["title"] = normalizeString(
                xbmc.getInfoLabel("VideoPlayer.TVshowtitle")
            )  # Show
        if item["title"] == "":
            item["title"] = normalizeString(
                xbmc.getInfoLabel("VideoPlayer.OriginalTitle")
            )  # try to get original title
        item["file_original_path"] = unquote(
            xbmc.Player().getPlayingFile()
        )  # Full os.path of a playing file
        item["file_original_path"] = item["file_original_path"].split("?")
        item["file_original_path"] = os.path.basename(item["file_original_path"][0])[
            :-4
        ]

    else:  # Take item params from window when kodi is not playing
        labelIMDB = xbmc.getInfoLabel("ListItem.IMDBNumber")
        item["year"] = xbmc.getInfoLabel("ListItem.Year")
        item["season"] = xbmc.getInfoLabel("ListItem.Season")
        item["episode"] = xbmc.getInfoLabel("ListItem.Episode")
        item["file_original_path"] = ""
        labelType = xbmc.getInfoLabel("ListItem.DBTYPE")  # movie/tvshow/season/episode
        isItMovie = labelType == "movie" or xbmc.getCondVisibility(
            "Container.Content(movies)"
        )
        isItEpisode = labelType == "episode" or xbmc.getCondVisibility(
            "Container.Content(episodes)"
        )

        if isItMovie:
            item["title"] = xbmc.getInfoLabel("ListItem.OriginalTitle")
        elif isItEpisode:
            item["title"] = xbmc.getInfoLabel("ListItem.TVShowTitle")
        else:
            item[
                "title"
            ] = "SearchFor..."  # In order to show "No Subtitles Found" result.

    log(f"item: {item}")
    imdb_id = 0
    try:
        if (
            xbmc.Player().isPlaying()
        ):  # Enable using subtitles search dialog when kodi is not playing
            playerid_query = (
                '{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
            )
            playerid = loads(xbmc.executeJSONRPC(playerid_query))["result"][0]["playerid"]
            imdb_id_query = (
                '{"jsonrpc": "2.0", "method": "Player.GetItem", "params": {"playerid": '
                + str(playerid)
                + ', "properties": ["imdbnumber"]}, "id": 1}'
            )
            imdb_id = loads(xbmc.executeJSONRPC(imdb_id_query))["result"]["item"][
                "imdbnumber"
            ]
            log(f"imdb JSONPC: {imdb_id}")
        else:
            if labelIMDB:
                imdb_id = labelIMDB
            else:
                if isItMovie:
                    imdb_id = (
                        "ThisIsMovie"  # Search the movie by item['title'] for imdb_id
                    )
                elif isItEpisode:
                    imdb_id = "ThisIsEpisode"  # Search by item['title'] for tvdb_id
                else:
                    imdb_id = "tt0"  # In order to show "No Subtitles Found" result => Doesn't recognize movie/episode
    except Exception as err:
        log(f"Caught Exception: error in imdb id: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        pass

    if isinstance(imdb_id, str) and imdb_id[:2] == "tt":  # Simple IMDB_ID
        searchByIMDB(
            imdb_id, item["season"], item["episode"], item["file_original_path"]
        )
    else:
        # Search TV Show by Title
        if item["season"] or item["episode"]:
            try:
                imdb_id = searchTMDB("tv", quote(item["title"]), 0)
                log(f"Search TV TMDB:{imdb_id} [{item['title']}]")
                if isinstance(imdb_id, str) and imdb_id[:2] == "tt":
                    searchByIMDB(
                        imdb_id,
                        item["season"],
                        item["episode"],
                        item["file_original_path"],
                    )
            except Exception as err:
                log(
                    f"Caught Exception: error in tv search: {format(err)}",
                    xbmc.LOGERROR,
                )
                log(format_exc(), xbmc.LOGERROR)
                pass
        # Search Movie by Title+Year
        else:
            try:
                imdb_id = searchTMDB("movie", query=item["title"], year=item["year"])
                log(f"Search TMDB:{imdb_id}")
                if not isinstance(imdb_id, str) or not imdb_id[:2] == "tt":
                    imdb_id = searchTMDB(
                        "movie", query=item["title"], year=(int(item["year"]) - 1)
                    )
                    log(f"Search IMDB(2):{imdb_id}")
                if isinstance(imdb_id, str) and imdb_id[:2] == "tt":
                    searchByIMDB(imdb_id, 0, 0, item["file_original_path"])
            except Exception as err:
                log(
                    f"Caught Exception: error in movie search: {format(err)}",
                    xbmc.LOGERROR,
                )
                log(format_exc(), xbmc.LOGERROR)
                pass

    # Search Local File
    if not imdb_id:
        ManualSearch(item["title"])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    if __addon__.getSetting("Debug") == "true":
        if isinstance(imdb_id, str) and imdb_id[:2] == "tt":
            Dialog().ok(str(item), "imdb: " + str(imdb_id))
        else:
            Dialog().ok(str(item), "NO IDS")

elif action == "manualsearch":
    searchstring = getParam("searchstring", params)
    ManualSearch(searchstring)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif action == "download":
    id = getParam("id", params)
    log(f"Download ID: {id}")
    subs = download(id)
    for sub in subs:
        listitem = ListItem(label=sub)
        xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False
        )
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    Ap = 0

    uploadAP(params)

elif action == "clean":
    try:
        xbmcvfs.rmtree(__profile__)
    except Exception as err:
        log(f"Caught Exception: deleting tmp dir: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        pass
    xbmc.executebuiltin(f"Notification({__name__},{__language__(32004)}")
