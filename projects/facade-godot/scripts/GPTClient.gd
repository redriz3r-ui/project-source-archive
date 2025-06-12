class_name GPTClient
extends Node

# Constants for intent categories
const ACTIONS = {
	"greet": ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "sup", "yo"],
	"farewell": ["bye", "goodbye", "see you", "farewell", "take care", "until next time", "later", "peace out", "stop"],
	"physical": {
		"hug": ["hug", "embrace", "hold", "cuddle", "snuggle"],
		"kiss": ["kiss", "peck", "smooch", "make out"],
		"touch": ["touch", "hold hands", "caress", "stroke", "pat"],
		"dance": ["dance", "waltz", "sway", "move to music"],
		"attack": ["kill", "hit", "punch", "attack", "hurt", "harm", "fight"],
		"intimate": ["sex", "make love", "sleep with", "intimate"]
	},
	"emotional": {
		"apologize": ["sorry", "apologize", "forgive", "regret", "my bad", "my mistake"],
		"thank": ["thank", "thanks", "appreciate", "grateful"],
		"praise": ["good job", "well done", "amazing", "impressive", "brilliant", "excellent", "wow", "incredible"],
		"comfort": ["comfort", "console", "there there", "it's okay", "don't worry"],
		"insult": ["stupid", "idiot", "dumb", "fool", "worthless"],
		"hate": ["hate", "despise", "loathe", "can't stand"]
	},
	"social": {
		"invite": ["come", "join", "accompany", "hang out", "spend time"],
		"share": ["share", "tell", "confide", "reveal", "open up"],
		"ask": ["can you", "would you", "could you", "please", "may i", "do you want", "would you like"],
		"offer": ["offer", "give", "present", "bring", "get you", "want to give", "have this", "take this"],
		"call": ["call", "name", "address", "refer to"]
	},
	"romantic": {
		"flirt": ["flirt", "charm", "woo", "sweet talk", "compliment"],
		"propose": ["marry", "propose", "spend life", "forever", "together"],
		"date": ["date", "go out", "dinner", "movie", "coffee"],
		"love": ["love", "adore", "cherish", "fond", "affectionate"]
	}
}

const EMOTIONS = {
	"happy": ["happy", "joy", "glad", "delighted", "cheerful", "excited", "thrilled", "ecstatic", "elated", "jubilant", "amazing", "wow"],
	"sad": ["sad", "upset", "sorry", "depressed", "down", "blue", "miserable", "heartbroken", "gloomy", "melancholy"],
	"angry": ["angry", "mad", "furious", "enraged", "irritated", "annoyed", "frustrated", "outraged", "livid", "fuming", "hate", "kill"],
	"loving": ["love", "adore", "cherish", "fond", "affectionate", "tender", "passionate", "devoted", "caring", "warm"],
	"afraid": ["afraid", "scared", "frightened", "terrified", "anxious", "worried", "nervous", "fearful", "panicked"],
	"surprised": ["surprised", "shocked", "amazed", "astonished", "stunned", "bewildered", "startled"],
	"disgusted": ["disgusted", "repulsed", "revolted", "appalled", "horrified", "sickened"],
	"neutral": ["fine", "okay", "alright", "so-so", "meh", "whatever"]
}

const TARGETS = {
	"self": ["i ", "me ", "my ", "mine", "myself"],
	"other": ["you", "your", "yours", "yourself", "u "],
	"both": ["we", "us", "our", "ours", "ourselves", "together"]
}

# Common names to detect
const COMMON_NAMES = ["alex", "robin", "sam", "jordan", "taylor", "casey", "jamie", "morgan"]

func _ready() -> void:
	print("[GPTClient] Initialized. Ready to parse intents via rule-based system.")

func _check_category(text: String, category: Dictionary) -> String:
	for key in category:
		if category[key] is Array:
			for word in category[key]:
				if text.contains(word):
					return key
		elif category[key] is Dictionary:
			var subcategory = _check_category(text, category[key])
			if subcategory != "":
				return key + "_" + subcategory
	return ""

func _detect_emotion(text: String) -> String:
	for emotion in EMOTIONS:
		for word in EMOTIONS[emotion]:
			if text.contains(word):
				return emotion
	return "neutral"

func _detect_name(text: String) -> String:
	for name in COMMON_NAMES:
		if text.contains(name):
			return name
	return ""

func _detect_target(text: String) -> String:
	# First check for explicit target words
	for target in TARGETS:
		for word in TARGETS[target]:
			if text.contains(word):
				return target
	
	# If no explicit target, check the action type
	if text.contains("love") or text.contains("hate") or text.contains("kill"):
		return "other"
	
	# If there's a name in the text, it's likely directed at that person
	if _detect_name(text) != "":
		return "other"
	
	return "self"

func _count_letter_repetition(text: String) -> float:
	var max_repetition = 0
	var current_char = ""
	var current_count = 1
	
	for i in range(text.length()):
		var char = text[i]
		if char == current_char:
			current_count += 1
			max_repetition = max(max_repetition, current_count)
		else:
			current_char = char
			current_count = 1
	
	return max_repetition

func parse_input(input_text: String) -> Dictionary:
	print("[GPTClient] parse_input called with: ", input_text)
	
	# Convert input to lowercase for easier matching
	var text := input_text.to_lower()
	
	# Default intent
	var intent := {
		"action": "talk",
		"emotion": "neutral",
		"target": "self",
		"intensity": 1.0,
		"name": ""
	}
	
	# Detect name if present
	var detected_name = _detect_name(text)
	if detected_name != "":
		intent["name"] = detected_name
		intent["action"] = "social_call"
	
	# Detect action
	var detected_action = _check_category(text, ACTIONS)
	if detected_action != "":
		intent["action"] = detected_action
	
	# Detect emotion
	intent["emotion"] = _detect_emotion(text)
	
	# Detect target
	intent["target"] = _detect_target(text)
	
	# Detect intensity through word repetition or emphasis
	var exclamation_count = text.count("!")
	var question_count = text.count("?")
	var caps_count = 0
	for char in text:
		if char == char.to_upper() and char != char.to_lower():
			caps_count += 1
	
	# Calculate intensity based on emphasis markers
	intent["intensity"] = 1.0 + (exclamation_count * 0.2) + (caps_count * 0.01)
	
	# Add intensity for letter repetition (e.g., "LOVEEE")
	var letter_repetition = _count_letter_repetition(text)
	if letter_repetition > 2:
		intent["intensity"] += 0.1 * (letter_repetition - 2)
	
	# Boost intensity for certain emotions and actions
	if intent["emotion"] in ["angry", "loving", "happy"]:
		intent["intensity"] += 0.3
	if intent["action"] in ["physical_attack", "romantic_love", "emotional_hate"]:
		intent["intensity"] += 0.3
		
	# Boost intensity for repeated words
	var words = text.split(" ")
	var word_count = {}
	for word in words:
		if word_count.has(word):
			word_count[word] += 1
		else:
			word_count[word] = 1
	
	for count in word_count.values():
		if count > 1:
			intent["intensity"] += 0.1 * (count - 1)
		
	intent["intensity"] = min(intent["intensity"], 2.0)  # Cap at 2.0
	
	print("[GPTClient] Parsed intent: ", intent)
	return intent 
