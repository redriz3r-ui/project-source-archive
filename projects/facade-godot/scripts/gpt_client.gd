class_name GPTClient

# Simple keyword-based intent detection for MVP
const INTENT_KEYWORDS = {
	"accuse": ["blame", "fault", "wrong", "mistake", "your fault"],
	"comfort": ["sorry", "apologize", "regret", "feel bad", "didn't mean"],
	"deflect": ["whatever", "doesn't matter", "forget it", "never mind"],
	"confront": ["why", "how could you", "explain", "tell me"],
	"support": ["help", "support", "together", "we can", "let's"]
}

func parse_input(text: String) -> Dictionary:
	var lowercase_text = text.to_lower()
	var intent = "neutral"
	var target = "both"
	
	# Check for target
	if lowercase_text.contains("alex"):
		target = "alex"
	elif lowercase_text.contains("robin"):
		target = "robin"
	
	# Check for intent
	for intent_type in INTENT_KEYWORDS:
		for keyword in INTENT_KEYWORDS[intent_type]:
			if lowercase_text.contains(keyword):
				intent = intent_type
				break
		if intent != "neutral":
			break
	
	return {
		"intent": intent,
		"target": target,
		"text": text
	} 
