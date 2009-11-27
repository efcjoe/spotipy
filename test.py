from spotipy import spotipy

if __name__ == '__main__':
	s = spotipy()
	d = s.lookup_track(uri='spotify:track:2kf767S4oj5KKVLZKEG4gw')
	print d