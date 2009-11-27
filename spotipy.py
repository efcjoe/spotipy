import logging
logging.basicConfig(
    level = logging.DEBUG,
    datefmt='%a, %d %b %Y %H:%M:%S',
    format = '\033[93m\n* LOGGING **********************\n%(asctime)s %(levelname)s: \033[95m%(message)s\033[93m\n********************************\n\033[0m',
)

import urllib2
try:
	import xml.etree.cElementTree as ET
except ImportError:
	try:
		import xml.etree.ElementTree as ET
	except ImportError:
		raise spotipyError('ElementTree must be installed before pyspotify will work.')

class spotipyError(Exception):
	def __repr__(self):
		return '<spotipy.%s: %s>' % (self.__class__.__name__, self.message)

class ConnectionError(spotipyError): pass

class spotipy(object):
	def lookup_track(self, **kwargs):
		s = SpotifyLookup('track', kwargs)
		return s.do()

class GenericPropertyObject(object):
	attributes = []
	
	def __init__(self, **kwargs):
		for a in self.attributes:
			self.__setattr__(a, None)
		for k in kwargs:
			self.__setattr__(k, kwargs.get(k))

class Artist(GenericPropertyObject):
	attributes = ['name', 'uri']
	
	def __repr__(self):
		return "<spotipy.Artist: %s>" % self.name
	
class Album(GenericPropertyObject):
	attributes = ['title', 'uri', 'artist', 'availability', 'released', 'ids']

	def __repr__(self):
		return "<spotipy.Album: %s>" % self.title

class Track(GenericPropertyObject):
	attributes = ['title', 'artist', 'album', 'uri', 'ids', 'number', 'length', 'popularity', 'disc_number']

	def __repr__(self):
		return "<spotipy.Track: %s>" % self.title

class DataInterpreter(object):
	_data = None
	parent_map = None
	base_tag = None
	final_dictionary = []
	formatted_dictionary = []
	root_locations = {}
	root_counter = 0
	
	def __init__(self, data):
		self._data = data
		self.generate_parent_map()
		self.iterate_tags()
	
	def add_tag(self, tag):
		# If the tag has no parent, it is the base tag (ie. <html> on a HTML page)
		if not self.parent_map.get(tag.get('object')):
			self.base_tag = tag.get('object')
		# If it does have a parent, it is at least inside the base tag
		else:
			# If the parent of this tag is the base tag, we don't want it to have a parent in our dictionary
			if self.parent_map.get(tag.get('object')) == self.base_tag:
				parent = None
			else:
				# Otherwise, it is at least 3 levels into the page, so the parent must be recorded
				parent = self.parent_map.get(tag.get('object'))
			
			# Add the parent key to the tag dictionary
			tag['parent'] = parent
			
			if not parent:
				# If the tag has no parent, we can add it to the list as a new section
				self.final_dictionary.append([tag])
				# We'll add it to root tag locations as well so we can easily pinpoint stuff in this list
				in_root_locations = True
				try:
					self.root_locations[tag.get('tag')]
				except:
					in_root_locations = False
				
				# We'll use the full tag name and the formatted tag name to avoid annoyances. It's not a big difference.
				if in_root_locations:
					self.root_locations[tag.get('tag')].append(self.root_counter)
					self.root_locations[self.format_value('tag', tag.get('tag'))].append(self.root_counter)
				else:
					self.root_locations[tag.get('tag')] = [self.root_counter,]
					self.root_locations[self.format_value('tag', tag.get('tag'))] = [self.root_counter,]
				self.root_counter += 1
			else:
				# If the tag has a parent, find the list we were working on last (lucky XML is sequential)
				last_updated = self.final_dictionary[-1]
				count = 0
				for x in last_updated:
					# Find the parent tag of the root tag we are adding
					if tag.get('parent') == x.get('object'):
						# Change the parent property to the ID of its parent in the list
						tag['parent'] = count
						break
					count += 1
				last_updated.append(tag)

	def generate_parent_map(self):
		# Generate a map of {<tag>: <parent>, <tag>: <parent>}
		self.parent_map = dict((c, p) for p in self._data.getiterator() for c in p)
	
	def format_value(self, key, value):
		try:
			r = {
				'tag': lambda value: value.split('}')[1],
				'text': lambda value: value.strip(' \n')
			}.get(key)(value)
		except:
			r = value
		return r
	
	def iterate_tags(self):
		for t in self._data.getiterator():
			self.add_tag(
				{
					'object': t,
					'tag': t.tag,
					'attrs': t.attrib,
					'text': t.text,
				}
			)
	
	def get(self, non_formatted = False):
		# This runs the final dictionary through the format_value loop (unless non_formatted = True)
		if non_formatted:
			return self.Data(self.final_dictionary)
		if self.formatted_dictionary:
			return self.Data(self.formatted_dictionary)
		self.formatted_dictionary = []
		for x in self.final_dictionary:
			inner_list = []
			for l in x:
				d = {}
				for k, v in l.items():
					d.update({k: self.format_value(k, v)})
				inner_list.append(d)
			self.formatted_dictionary.append(inner_list)
		return self.Data(self.formatted_dictionary)

	class Data(object):
		dictionary = None
		
		def __init__(self, dictionary):
			self.dictionary = dictionary
		
		def __repr__(self):
			return "<spotipy.DataInterpreter.Data>"
		
		def _parent(self):
			return DataInterpreter
		
		def _get_root_locations(self, search):
			try:
				return self._parent().root_locations.get(search)
			except:
				return False
		
		def _get_root_elements(self, tag_name):
			root_locations = self._get_root_locations(tag_name)
			root_elements = [self.dictionary[x] for x in root_locations]
			return root_elements
		
		def get_tag(self, *args):
			root_element = self._get_root_elements(args[0])[0]
			
			if len(args) == 1:
				return self.Tag(**root_element[0])
			elif len(args) == 2:
				# The ultimate tag will have this as its parent...
				parent = 0
			else:
				# The ultimate tag will have this as its parent...
				parent = len(args[1:])
				
			# ...and this as its name
			name = args[-1]
			
			# Search for it in root_element
			count = 0
			element = None
			for e in root_element:
				if e.get('parent') == parent and e.get('tag') == name:
					element = e
				count += 1
			
			try:
				return self.Tag(**element)
			except TypeError:
				return None
		
		def get_tags(self, *args):
			#
			# TODO
			# Mutli-level get_tags, eg. 'album' (x3) -> 'availability' -> 'territories' (x2)
			# (maybe)... Not sure if this is needed
			#
			root_elements = self._get_root_elements(args[0])
			final_elements = []
			for r in root_elements:
				final_elements.append(self.Tag(**r[0]))
			return final_elements
		
		class Tag(GenericPropertyObject):
			attributes = ['tag', 'text', 'attrs', 'object']
		
			def __repr__(self):
				return "<spotipy.Data.Tag: %s>" % self.tag

class GenericRequest(object):
	actions = None
	action = None
	args = None
	service_base = None
	raw_response = None
	
	def __init__(self, action, args):
		# Check if we're performing a valid action
		self._validate_action(action)
		
		# Make sure we're using the right arguments
		# First, we'll check we have the required arguments
		reqd = self.actions.get(action)[1].get('required')
		errors = 0
		for r in reqd:
			if r not in args:
				errors += 1
		if errors > 0:
			raise spotipyError('Did not pass spotipy the required arguments (%s) for action: %s' % (str(reqd), action))
		
		# Now we'll make sure that no weird args are trying to be passed
		opts = self.actions.get(action)[1].get('optional')
		
		bad_args = []
		errors = 0
		for a in args:
			if a not in reqd and a not in opts:
				bad_args.append(a)
				errors += 1
		if errors > 0:
			raise spotipyError('Trying to pass unsupported arguments (%s) for action: %s' % (str(bad_args), action))
		
		# If the required fields are ordered in a dictionary...
		if self._is_dictionary(reqd):
			# ...this means they can only have specific values
			errors = []
			for k in reqd:
				if k in args:
					passed = args.get(k)
					if passed not in reqd[k]:
						errors.append(k)
			if errors:
				raise spotipyError('Trying to pass unsupported arguments for attributes: %s' % (str(errors)))
		
		# If the optional fields are ordered in a dictionary...
		if self._is_dictionary(opts):
			# ...this means they can only have specific values
			errors = []
			for k in opts:
				if k in args:
					passed = args.get(k)
					if passed not in opts[k]:
						errors.append(k)
			if errors:
				raise spotipyError('Trying to pass unsupported arguments for attributes: %s' % (str(errors)))
		
		# All args are valid, so these can be used at any time by the user
		self.action = action
		self.args = args
	
	def do(self):
		# Everything is in order, run the mapped function
		return self.actions.get(self.action)[0]()
	
	def _validate_action(self, action):
		if action in self.actions:
			return True
		raise spotipyError('Tried to perform an action (%s) which is not possible with %s' % (action, self.__class__.__name__))
	
	def _is_dictionary(self, d):
		if d.__class__.__name__ == 'dict':
			return True
		return False
	
	def construct_url(self):
		query_string = '?'
		for a in self.args:
			query_string += (a + '=' + self.args.get(a) + '&')
		url = self.service_base
		return (url + query_string).rstrip('&')
	
	def fetch_data(self):
		url = self.construct_url()
		request = urllib2.build_opener()
		#request.addheaders = [('User-agent', 'spotipy/Python-urllib')]
		try:
			request = request.open(url)
		except urllib2.HTTPError:
			raise ConnectionError('spotipy could not open the created url (%s). This could mean 1) the spotify API is down, 2) your server cannot access spotify, or 3) spotify could not find anything in its catalogue with the attributes passed to it.' % url)
		self.raw_response = request.read()
		return self.raw_response
	
	def interpret_data(self, data = None):
		if data == None: data = self.raw_response
		interpreter = DataInterpreter(ET.XML(data))
		return interpreter
		
class SpotifyLookup(GenericRequest):
	def __init__(self, action, args):
		self.actions = {
			'track': [
				self.lookup_track,
				{
					'required': ('uri',),
					'optional': {'extras': ('album', 'albumdetail', 'track', 'trackdetail',)}
				}
			],
		}
		self.service_base = 'http://ws.spotify.com/lookup/1/'
		GenericRequest.__init__(self, action, args)
	
	def _validate_uri(self, uri):
		try:
			re
		except NameError:
			import re
		regexp = re.compile('(spotify)(:)(artist|album|track)(:).*?((?:[a-z][a-z]*[0-9]+[a-z0-9]*))',re.IGNORECASE|re.DOTALL)
		s = regexp.search(uri)
		if s:
			return True
		return False
	
	def lookup_track(self):
		if self._validate_uri(self.args.get('uri')):
			raw_data = self.fetch_data()
			interpreter = self.interpret_data()
			d = interpreter.get()
			artist = Artist(
				name = d.get_tag('artist', 'name').text,
				uri = d.get_tag('artist').attrs.get('href'),
			)
			album = Album(
				title = d.get_tag('album', 'name').text,
				uri = d.get_tag('album').attrs.get('href'),
				availability = d.get_tag('album', 'availability', 'territories').text,
				artist = artist,
			)
			id_dictionary = {}
			for x in d.get_tags('id'):
				id_dictionary.update({x.attrs.get('type'): {'text': x.text, 'href': x.attrs.get('href', None)}})
			track = Track(
				title = d.get_tag('name').text,
				artist = artist,
				album = album,
				uri = self.args.get('uri'),
				ids = id_dictionary,
				number = d.get_tag('track-number').text,
				length = d.get_tag('length').text,
				popularity = d.get_tag('popularity').text
			)
			return track
		raise spotipyError('The spotify uri given to spotipy did not match the proper format.')