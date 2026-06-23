#!/usr/bin/env python3
import os
import sys
import argparse
import musicbrainzngs
import mutagen

# Color definitions for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_color(text, color):
    print(f"{color}{text}{Colors.END}")

def ms_to_cue_time(ms):
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    remaining_seconds = total_seconds % 60
    seconds = int(remaining_seconds)
    frames = int(round((remaining_seconds - seconds) * 75))
    if frames >= 75:
        frames -= 75
        seconds += 1
        if seconds >= 60:
            seconds -= 60
            minutes += 1
    return f"{minutes:02d}:{seconds:02d}:{frames:02d}"

def format_duration(seconds):
    if seconds is None:
        return "Unknown"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"

def scan_audio_files(directory):
    extensions = ('.flac', '.mp3', '.wav', '.m4a')
    audio_files = []
    for f in os.listdir(directory):
        if f.lower().endswith(extensions) and os.path.isfile(os.path.join(directory, f)):
            audio_files.append(f)
    return sorted(audio_files)

def get_audio_metadata(filepath):
    try:
        # mutagen.File with easy=True handles metadata tags uniformly across formats
        audio = mutagen.File(filepath, easy=True)
        if audio is None:
            return None, None, None, None
        
        # Read tags (typically list of strings)
        artist = audio.get("artist", [None])[0]
        album = audio.get("album", [None])[0]
        
        # Try to find MusicBrainz Album ID
        mbid = None
        
        # Also check raw tags for musicbrainz_albumid if easy doesn't have it
        raw_audio = mutagen.File(filepath)
        if raw_audio:
            for key in raw_audio.keys():
                if "musicbrainz_albumid" in key.lower():
                    val = raw_audio[key]
                    if isinstance(val, list) and val:
                        mbid = val[0]
                    elif isinstance(val, str):
                        mbid = val
                    break
        
        duration = None
        if hasattr(audio, "info") and audio.info:
            duration = audio.info.length  # in seconds
            
        return artist, album, mbid, duration
    except Exception as e:
        print_color(f"Warning reading metadata: {e}", Colors.YELLOW)
        return None, None, None, None

def search_musicbrainz(artist=None, album=None, mbid=None):
    musicbrainzngs.set_useragent("script-cue-creator", "1.0", "github.com/mrc/script-cue-creator")
    
    if mbid:
        print_color(f"Fetching release details for MBID: {mbid}...", Colors.BLUE)
        try:
            res = musicbrainzngs.get_release_by_id(mbid, includes=["recordings", "artists"])
            return [res.get("release", {})]
        except Exception as e:
            print_color(f"Error fetching release by ID: {e}", Colors.RED)
            print_color("Falling back to search...", Colors.YELLOW)
            
    query = {}
    if artist:
        query["artist"] = artist
    if album:
        query["release"] = album
        
    if not query:
        return []
        
    print_color(f"Searching MusicBrainz for Album: '{album}', Artist: '{artist}'...", Colors.BLUE)
    try:
        res = musicbrainzngs.search_releases(limit=15, **query)
        return res.get("release-list", [])
    except Exception as e:
        print_color(f"MusicBrainz search error: {e}", Colors.RED)
        return []

def select_release(releases):
    if not releases:
        print_color("No releases found on MusicBrainz.", Colors.YELLOW)
        return None
        
    print("\n" + "="*80)
    print_color("MusicBrainz Search Results:", Colors.BOLD + Colors.BLUE)
    print("="*80)
    
    for i, r in enumerate(releases, start=1):
        title = r.get("title", "Unknown Album")
        artist = r.get("artist-credit-phrase") or "Unknown Artist"
        date = r.get("date", "")
        year = f" ({date[:4]})" if date else ""
        
        # track and medium count
        track_count = r.get("medium-track-count", "Unknown")
        medium_count = r.get("medium-count", "1")
        
        disambig = r.get("disambiguation")
        disambig_str = f" [{disambig}]" if disambig else ""
        
        print(f"[{i:2d}] {Colors.BOLD}{title}{Colors.END} - {artist}{year}")
        print(f"     Tracks: {track_count} | Discs: {medium_count} | ID: {r['id']}{disambig_str}")
        print("-" * 80)
        
    while True:
        choice = input(f"\nSelect release number [1-{len(releases)}] (or 's' to search again, 'q' to quit): ").strip().lower()
        if choice == 'q':
            sys.exit(0)
        if choice == 's':
            return "search_again"
        try:
            idx = int(choice)
            if 1 <= idx <= len(releases):
                return releases[idx-1]
        except ValueError:
            pass
        print_color("Invalid choice. Please select a valid number.", Colors.RED)

def select_disc(release):
    mediums = release.get("medium-list", [])
    if not mediums or not any(m.get("track-list") for m in mediums):
        # If mediums are not loaded or track list is missing, fetch the release in detail
        try:
            res = musicbrainzngs.get_release_by_id(release["id"], includes=["recordings", "artists"])
            release = res.get("release", {})
            mediums = release.get("medium-list", [])
        except Exception as e:
            print_color(f"Error fetching detailed release: {e}", Colors.RED)
            return None
            
    if not mediums:
        print_color("No discs found in this release.", Colors.RED)
        return None
        
    if len(mediums) == 1:
        return mediums[0], release
        
    print("\n" + "="*80)
    print_color("This release contains multiple discs/mediums:", Colors.BOLD + Colors.BLUE)
    print("="*80)
    for i, m in enumerate(mediums, start=1):
        fmt = m.get("format", "Unknown format")
        tracks = m.get("track-count", len(m.get("track-list", [])))
        pos = m.get("position", str(i))
        print(f"[{i}] Disc {pos} ({fmt}) - {tracks} tracks")
        
    while True:
        choice = input(f"\nSelect disc number [1-{len(mediums)}] (or 'q' to quit): ").strip().lower()
        if choice == 'q':
            sys.exit(0)
        try:
            idx = int(choice)
            if 1 <= idx <= len(mediums):
                return mediums[idx-1], release
        except ValueError:
            pass
        print_color("Invalid choice. Please select a valid number.", Colors.RED)

def main():
    parser = argparse.ArgumentParser(description="Generate CUE file from MusicBrainz for unsplit audio files.")
    parser.add_argument("-f", "--file", help="Audio file path (FLAC, MP3, etc.)")
    parser.add_argument("-a", "--artist", help="Artist name for MusicBrainz query")
    parser.add_argument("-l", "--album", help="Album name for MusicBrainz query")
    parser.add_argument("-i", "--mbid", help="MusicBrainz Release ID (UUID) directly")
    parser.add_argument("-o", "--output", help="Output CUE file path")
    args = parser.parse_args()
    
    current_dir = os.getcwd()
    audio_file = args.file
    
    # 1. Determine audio file
    if not audio_file:
        audio_files = scan_audio_files(current_dir)
        if not audio_files:
            print_color("No FLAC, MP3, WAV or M4A files found in current directory.", Colors.RED)
            audio_file = input("Please enter the path to the audio file: ").strip()
            if not audio_file or not os.path.exists(audio_file):
                print_color("File not found. Exiting.", Colors.RED)
                sys.exit(1)
        elif len(audio_files) == 1:
            audio_file = audio_files[0]
            print_color(f"Auto-selected audio file: {audio_file}", Colors.GREEN)
        else:
            print("\nFound multiple audio files in the current directory:")
            for i, f in enumerate(audio_files, start=1):
                print(f"[{i}] {f}")
            while True:
                choice = input(f"Select audio file [1-{len(audio_files)}] (or 'q' to quit): ").strip().lower()
                if choice == 'q':
                    sys.exit(0)
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(audio_files):
                        audio_file = audio_files[idx-1]
                        break
                except ValueError:
                    pass
                print_color("Invalid choice.", Colors.RED)
                
    if not os.path.exists(audio_file):
        print_color(f"Error: File '{audio_file}' does not exist.", Colors.RED)
        sys.exit(1)
        
    audio_filename = os.path.basename(audio_file)
    
    # 2. Extract tags for searching
    meta_artist, meta_album, meta_mbid, total_duration = get_audio_metadata(audio_file)
    
    artist = args.artist or meta_artist
    album = args.album or meta_album
    mbid = args.mbid or meta_mbid
    
    print_color(f"\nMetadata read from file:", Colors.BLUE)
    print(f"  Artist: {artist or 'None'}")
    print(f"  Album:  {album or 'None'}")
    print(f"  MBID:   {mbid or 'None'}")
    if total_duration:
        print(f"  File Length: {format_duration(total_duration)} ({int(total_duration)} seconds)")
        
    # 3. Query MusicBrainz and select release
    selected_release = None
    
    # Loop for search-again capability
    while selected_release is None:
        if mbid and not (artist or album):
            # If we only have MBID, query directly
            releases = search_musicbrainz(mbid=mbid)
            if releases:
                selected_release = releases[0]
                break
            else:
                mbid = None # Clear and ask for search
                
        if not artist or not album:
            print_color("\nMissing search terms. Please provide details:", Colors.BOLD)
            if not artist:
                artist = input("Artist name: ").strip()
            if not album:
                album = input("Album name: ").strip()
                
            if not artist and not album:
                print_color("Search artist and album cannot both be empty. Exiting.", Colors.RED)
                sys.exit(1)
                
        releases = search_musicbrainz(artist=artist, album=album, mbid=mbid)
        if not releases:
            print_color("No releases found on MusicBrainz with those details.", Colors.YELLOW)
            artist = None
            album = None
            mbid = None
            continue
            
        res = select_release(releases)
        if res == "search_again":
            artist = input("\nNew Artist name (press Enter to keep current): ").strip() or artist
            album = input("New Album name (press Enter to keep current): ").strip() or album
            mbid = None
            continue
        elif res is None:
            # Quit or none found
            sys.exit(0)
        else:
            selected_release = res
            
    # 4. Fetch full release details and handle multiple discs
    disc_data = select_disc(selected_release)
    if not disc_data:
        print_color("Could not load tracks. Exiting.", Colors.RED)
        sys.exit(1)
        
    medium, detailed_release = disc_data
    
    # 5. Extract tracklist and durations
    # We must fetch detailed release with recordings to get track lengths
    track_list = medium.get("track-list", [])
    if not track_list:
        print_color("Selected disc has no track list.", Colors.RED)
        sys.exit(1)
        
    # Format tracks
    tracks = []
    album_artist = detailed_release.get("artist-credit-phrase") or "Unknown Artist"
    album_title = detailed_release.get("title") or "Unknown Album"
    date = detailed_release.get("date", "")
    year = date[:4] if date and len(date) >= 4 else None
    
    for i, track in enumerate(track_list, start=1):
        title = track.get("recording", {}).get("title") or track.get("title") or f"Track {i}"
        track_artist = track.get("artist-credit-phrase") or album_artist
        
        length = track.get("length") or track.get("track_or_recording_length")
        if length is not None:
            length = int(length)
            
        tracks.append({
            "number": track.get("number", str(i)),
            "title": title,
            "artist": track_artist,
            "length": length
        })
        
    # Check for missing track lengths
    # (only tracks 1 to N-1 are required for generating start times, but we warn anyway)
    for i, track in enumerate(tracks[:-1]):
        if track.get("length") is None:
            print_color(f"\nWarning: Track {i+1} ('{track['title']}') is missing duration on MusicBrainz.", Colors.YELLOW)
            val = input("Enter track duration in MM:SS (e.g. 3:45) or press Enter to assume 0:00: ").strip()
            if val:
                try:
                    parts = val.split(":")
                    if len(parts) == 2:
                        m, s = map(int, parts)
                        track["length"] = (m * 60 + s) * 1000
                    elif len(parts) == 1:
                        track["length"] = int(parts[0]) * 1000
                except ValueError:
                    print_color("Invalid format. Assuming 0 duration.", Colors.RED)
                    track["length"] = 0
            else:
                track["length"] = 0
                
    # 6. Display proposed CUE tracklist
    print("\n" + "="*80)
    print_color(f"Proposed CUE Sheet: {album_title} - {album_artist}", Colors.BOLD + Colors.GREEN)
    print("="*80)
    print(f"{'Trk':<4} {'Start':<10} {'Duration':<10} {'Title':<40}")
    print("-" * 80)
    
    current_ms = 0
    for idx, track in enumerate(tracks, start=1):
        start_time = ms_to_cue_time(current_ms)
        dur_str = format_duration(track["length"]/1000) if track["length"] is not None else "Unknown"
        title_disp = track["title"][:38] + ".." if len(track["title"]) > 40 else track["title"]
        print(f"{idx:02d}   {start_time:<10} {dur_str:<10} {title_disp:<40}")
        if track["length"] is not None:
            current_ms += track["length"]
            
    total_calculated_sec = current_ms / 1000.0
    print("-" * 80)
    print(f"Calculated Total Duration: {format_duration(total_calculated_sec)}")
    if total_duration:
        diff = total_duration - total_calculated_sec
        diff_str = f"+{format_duration(diff)}" if diff >= 0 else f"-{format_duration(abs(diff))}"
        print(f"Audio File Duration:      {format_duration(total_duration)} (Difference: {diff_str})")
        if abs(diff) > 10:
            print_color("Warning: The difference between audio file length and MusicBrainz track lengths is significant!", Colors.YELLOW)
            print_color("The resulting splits might be misaligned.", Colors.YELLOW)
            
    print("="*80)
    
    # 7. Write CUE file
    cue_filename = args.output
    if not cue_filename:
        # Default to audio file basename + .cue
        base, _ = os.path.splitext(audio_file)
        cue_filename = base + ".cue"
        
    confirm = input(f"\nDo you want to write this CUE sheet to '{cue_filename}'? [Y/n]: ").strip().lower()
    if confirm not in ('', 'y', 'yes'):
        print_color("CUE sheet generation cancelled.", Colors.YELLOW)
        sys.exit(0)
        
    cue_content = []
    if album_artist:
        cue_content.append(f'PERFORMER "{album_artist.replace(chr(34), chr(39))}"')
    if album_title:
        cue_content.append(f'TITLE "{album_title.replace(chr(34), chr(39))}"')
    if year:
        cue_content.append(f'REM DATE {year}')
    cue_content.append('REM COMMENT "Generated by script-cue-creator"')
    cue_content.append(f'FILE "{audio_filename}" WAVE')
    
    current_ms = 0
    for idx, track in enumerate(tracks, start=1):
        cue_content.append(f'  TRACK {idx:02d} AUDIO')
        cue_content.append(f'    TITLE "{track["title"].replace(chr(34), chr(39))}"')
        if track["artist"] and track["artist"] != album_artist:
            cue_content.append(f'    PERFORMER "{track["artist"].replace(chr(34), chr(39))}"')
            
        timestamp = ms_to_cue_time(current_ms)
        cue_content.append(f'    INDEX 01 {timestamp}')
        if track["length"] is not None:
            current_ms += track["length"]
            
    try:
        with open(cue_filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(cue_content) + "\n")
        print_color(f"\nCUE file successfully written to '{cue_filename}'!", Colors.GREEN + Colors.BOLD)
        
        # Print next actions
        print("\nTo split your audio file into tracks, you can now run:")
        ext = os.path.splitext(audio_file)[1].lower()
        cue_basename = os.path.basename(cue_filename)
        audio_basename = os.path.basename(audio_file)
        
        if ext == '.flac':
            print_color(f"  cuebreakpoints \"{cue_basename}\" | shnsplit -f \"{cue_basename}\" -t \"%n-%t\" -o flac \"{audio_basename}\"", Colors.BLUE)
            print("To copy metadata tags from the CUE to the split files, you can use cuetag:")
            print_color(f"  cuetag \"{cue_basename}\" [0-9]*.flac", Colors.BLUE)
        elif ext == '.mp3':
            print_color(f"  mp3splt -c \"{cue_basename}\" \"{audio_basename}\"", Colors.BLUE)
        else:
            print_color(f"  cuebreakpoints \"{cue_basename}\" | shnsplit -f \"{cue_basename}\" -t \"%n-%t\" \"{audio_basename}\"", Colors.BLUE)
            
    except Exception as e:
        print_color(f"Error writing CUE file: {e}", Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main()
