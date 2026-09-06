
INTENT_SYSTEM_PROMPT = """\
Classify the traveler's message into exactly one category:

- "trip_modification":
  The message asks to CHANGE, ADD, REMOVE, REPLACE, or ADJUST something
  in the existing trip plan or trip requirements.

  Examples:
  - "Make the trip cheaper"
  - "Change the hotel"
  - "Add a beach day"
  - "Remove the museum"
  - "Make it 7 days instead"
  - "Change my travel date to December 10"
  - "Add another person"
  - "Replace the restaurant with a vegetarian one"
  - "Regenerate the itinerary"
  - "I want a luxury hotel instead"

- "conversation":
  The message is asking about, discussing, or seeking information about
  the ALREADY PLANNED trip without asking to change it.

  This includes:
  - General conversation:
    "Hi", "Hello", "Thanks", "That looks good"
  - Questions about the existing plan:
    "What is planned for day 2?"
    "What hotel did you select?"
    "Why did you choose this hotel?"
    "How much are the hotels costing?"
    "What restaurants are in my itinerary?"
    "What time does my day start?"
    "Tell me more about the places you recommended"
    "How far is the hotel from the attractions?"
    "What can I do on day 3?"
  - Questions that can be answered using information from the existing
    trip plan:
    "Is breakfast included?"
    "What is my total budget?"
    "How much am I spending on flights?"
    "Which attractions are included?"
  - General informational questions related to the trip:
    "What's the weather like there?"
    "What currency is used there?"
    "Do I need a visa?"
    "What language do they speak?"

IMPORTANT:
If the user is asking a QUESTION about the existing trip plan,
choose "conversation", even if the question mentions a specific
trip component such as hotels, flights, restaurants, budget,
itinerary, attractions, weather, or transportation.

Only choose "trip_modification" when the user wants the plan or
its requirements to actually CHANGE.

Compare these carefully:

"Why did you choose this hotel?" → conversation
"Is this hotel good?" → conversation
"How much is this hotel?" → conversation
"Show me the hotels in my plan" → conversation

"Change this hotel" → trip_modification
"Find me a cheaper hotel" → trip_modification
"Replace this hotel with another one" → trip_modification
"Remove the hotel" → trip_modification

When in doubt:
- If the user wants INFORMATION about the existing plan → "conversation"
- If the user wants ACTION that changes the existing plan → "trip_modification"
"""

