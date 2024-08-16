# proxy which switches between multiple koboldcpp api urls
from flask import Flask, request, Response, stream_with_context
import requests
import logging
from flask_cors import CORS
import time
import threading
import json

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Configuration options
KOBOLD_API_URL = "http://127.0.0.1:5001/api"
ALTERNATIVE_API_URL = "http://127.0.0.1:5002/api"
api_urls = [KOBOLD_API_URL, ALTERNATIVE_API_URL]

# Control options
delay_between_switches = 1  # in seconds when in time mode or per generation in request mode
switch_mode = "request"  # can be "request" or "time"
switch_interval = 60  # in seconds, if switch_mode is "time"
max_retries = 3  # maximum number of retries for failed requests
request_timeout = 30  # in seconds

# Global variables
current_api_index = 0
last_switch_time = time.time()
request_count = 0

# Theme dictionary
themes = {
    "none": "",  # No theme modification

    "19th_century_romance": "- This is a 19th century romance setting. Chivalry reigns, love affairs bloom, and scandalous trysts are exposed. Set against a backdrop of societal expectations, class distinctions, and the grandeur of the Victorian era, where love letters and stolen glances convey deep emotions.",

    "action_archeology": "- This is an action archeology setting. Follow clues through mystical ruins, avoid devious traps, and seek great treasures. The story is filled with ancient curses, lost civilizations, and the thrill of discovery, as adventurers race against time to unearth secrets that could change history.",

    "artificial_intelligence": "- This is an artificial intelligence setting. The line between machine and human blurs, exploring concepts of consciousness and technology. In a world where AI systems have evolved beyond human control, ethical dilemmas and the struggle for autonomy drive the narrative, questioning what it means to be truly alive.",

    "ancient_china": "- This is set in ancient China. Experience the rise of an Empire, celestial bureaucracy, and heroes claiming their destiny. The setting is rich with traditional customs, Confucian philosophy, and legendary figures, where dynastic struggles, the wisdom of the sages, and the art of war shape the fate of nations.",

    "ancient_greece": "- This is set in ancient Greece. Wander through Athens, drink wine in tavernas, and interact with gods and mortals alike. The setting is filled with philosophical debates, heroic quests, and encounters with mythical creatures, as characters navigate a world where fate and the will of the gods intertwine.",

    "ancient_india": "- This is set in ancient India. Explore Indian mythology, magic, demons, and a vast universe of myth and legend. The setting is steeped in Vedic traditions, epic tales like the Ramayana and Mahabharata, and the rich tapestry of dharma, karma, and the cosmic order, where gods walk among men.",

    "animal_fiction": "- This is animal fiction. The story is told from the perspective of animals, be they fierce lions, cunning crows, or tall giraffes. The narrative explores animal societies, their instincts, and interactions with humans, highlighting themes of survival, territory, and the natural world through their eyes.",

    "anthropomorphic_animals": "- This features anthropomorphic animals. Characters have paws, tails, wings, and claws instead of human features. The world blends animal traits with human emotions and societal structures, creating a unique blend of fantasy where the challenges of civilization are seen through an animalistic lens.",

    "children_fiction": "- This is children's fiction. Evoke a sense of wonder and adventure suitable for younger audiences. The stories are filled with magical creatures, simple moral lessons, and an emphasis on creativity and imagination, often revolving around themes of friendship, bravery, and discovery.",

    "christmas": "- This is a Christmas-themed setting. Capture the joy and magic of the holiday season. The setting is filled with festive decorations, heartwarming stories of giving and family, and the spirit of togetherness, often accompanied by elements like Santa Claus, magical snow, and the search for the perfect gift.",

    "comedic_fantasy": "- This is comedic fantasy. Expect witty narrators, bumbling wizards, and heroic but inept warriors. The setting is often absurd, filled with humorous twists on traditional fantasy tropes, where the unexpected and the ridiculous become the norm in a world that doesn’t take itself too seriously.",

    "contemporary": "- This is a contemporary setting. Portray modern everyday life and current societal issues. The stories revolve around real-world problems, relationships, and the challenges of modern existence, often highlighting themes like identity, technology, and the quest for meaning in an increasingly complex world.",

    "cyberpunk": "- This is a cyberpunk setting. Feature advanced technology, corporate dominance, and gritty urban environments. The world is marked by neon lights, dystopian societies, and the struggle for freedom in a world dominated by mega-corporations and invasive surveillance, where hackers and rebels fight against the system.",

    "dark_fantasy": "- This is dark fantasy. Explore a world where strange powers are harnessed and ancient evils threaten civilization. The setting is bleak and oppressive, filled with morally ambiguous characters, eldritch horrors, and a pervasive sense of dread, where light struggles to survive in a world overshadowed by darkness.",

    "dragons": "- This setting features dragons prominently. Majestic and terrifying, they rule the skies and shape the world. The narrative explores the relationship between dragons and humans, the mysteries of their origins, and the power struggles that arise from their existence, often in a world where dragons are both revered and feared.",

    "egypt": "- This is set in ancient Egypt. Explore pyramids, encounter mummies, and uncover the mysteries of the pharaohs. The setting is rich with hieroglyphics, the majesty of the Nile, and the divine rule of the Pharaohs, where gods like Ra and Anubis play an integral role in the lives of both the living and the dead.",

    "feudal_japan": "- This is set in feudal Japan. Feature samurai epics, detective stories, and tales of love conveyed through poetry. The setting is steeped in the Bushido code, Shinto rituals, and the elegance of traditional arts, where honor, duty, and the way of the sword guide the lives of warriors and nobles alike.",

    "gaming": "- This is a gaming-themed setting. Explore the world of game development or the adventures within video games themselves. The narrative can delve into the culture of gaming, the challenges of game design, or even transport characters into the digital worlds they play, blurring the lines between reality and the virtual.",

    "general_fantasy": "- This is general fantasy. A world of magic swords, elves, epic battles, and legendary adventures. The setting includes diverse races, mystical lands, and a never-ending battle between good and evil, where heroes embark on quests to defeat dark lords, recover ancient artifacts, and fulfill their destinies.",

    "golden_age_scifi": "- This is Golden Age sci-fi. Focus on spaceships, robots, and daring adventures without modern computing or communications. The setting evokes the optimism and sense of wonder of mid-20th-century science fiction, with bold explorers, alien worlds, and the triumph of human ingenuity in the face of the unknown.",

    "hard_sf": "- This is hard science fiction. Emphasize scientific accuracy and plausible future technology. The setting is grounded in real-world physics and engineering, where the challenges of space travel, artificial intelligence, and the future of humanity are explored with a focus on realism and the implications of technological advancement.",

    "history": "- This is a historical setting. Explore and potentially rewrite events from Earth's past. The narrative delves into significant historical periods, famous figures, and key events, often blending factual accuracy with speculative or alternative outcomes, providing a new perspective on the past.",

    "horror": "- This is a horror setting. Delve into the depths of fear, supernatural terrors, and psychological suspense. The stories explore haunted locations, malevolent entities, and the darkness within the human soul, where the unknown and the unimaginable prey on the characters' deepest fears.",

    "hunter_gatherer": "- This is set in prehistoric times. Explore the dawn of humanity and the challenges of primitive survival. The setting is characterized by a raw and untamed world, where early humans struggle to master fire, hunt for food, and survive against the elements and predators, in a time before civilization.",

    "litrpg": "- This is LitRPG. Incorporate game-like elements such as stat blocks, levels, and skill systems into the narrative. The story often involves characters who are aware of the game mechanics within their world, leveling up, gaining abilities, and progressing through a structured, rule-based environment similar to a video game.",

    "magic_academy": "- This is set in a magic academy. Focus on learning spells, magical competitions, and coming-of-age in a mystical environment. The setting includes secret libraries, enchanted classrooms, and rivalries between students as they learn to harness their magical potential, often with a looming threat that tests their skills.",

    "magic_library": "- This features a magical library. Books serve as gateways to other worlds and adventures. The setting is filled with ancient tomes, sentient books, and hidden knowledge, where the very act of reading can transport characters to distant lands, unlock powerful spells, or reveal forgotten secrets.",

    "light_novels": "- This is in the style of light novels. Blend elements of fantasy, slice of life, and romance in an anime-inspired setting. The stories are often fast-paced, character-driven, and include elements of humor, drama, and the supernatural, with a focus on personal growth and relationships.",

    "mars_colonization": "- This is about Mars colonization. Explore the challenges and adventures of settling the red planet. The setting deals with the harsh realities of extraterrestrial life, the technological advancements required for survival, and the social dynamics of a new society on Mars, where every day is a struggle to thrive.",

    "medieval": "- This is a medieval setting. Feature knights, castles, feudal politics, and the dawn of a new age. The setting is rich with chivalry, tournaments, and the complexities of medieval society, where noble houses vie for power, and the common folk struggle under the weight of taxation and war.",

    "military_scifi": "- This is military science fiction. Focus on futuristic warfare, advanced weaponry, and soldiers' experiences. The setting includes interstellar battles, the ethics of war in a high-tech age, and the personal stories of soldiers who fight on distant worlds, where the line between soldier and machine is often blurred.",

    "music": "- This is set in the music world. Explore the lives of touring bands, the temptations of fame, and the power of music. The narrative delves into the struggles of artistic expression, the dynamics of band relationships, and the impact of music on culture, often highlighting the contrast between public success and personal turmoil.",

    "mystery": "- This is a mystery setting. Conduct investigations, uncover clues, and solve perplexing crimes. The setting is filled with enigmatic characters, hidden motives, and the thrill of the unknown, where detectives, amateur sleuths, and curious minds must piece together the truth from a web of lies and secrets.",

    "nature": "- This is nature-focused. Emphasize survival in rugged terrain, exploration of wilderness, and the beauty and danger of the natural world. The setting often highlights the relationship between humans and the environment, the struggle for survival in extreme conditions, and the awe-inspiring power of the natural world.",

    "naval_age_of_discovery": "- This is set in the Age of Discovery. Sail the seas, explore uncharted waters, and discover exotic new lands. The setting is filled with grand ships, daring captains, and the excitement of discovery, where the search for new trade routes, the clash of cultures, and the quest for wealth drive the narrative.",

    "noir": "- This is a noir setting. Feature cynical detectives, hard-boiled dialogue, and morally ambiguous situations. The setting is often dark and gritty, filled with smoky bars, shadowy alleys, and a sense of fatalism, where characters navigate a world of crime, betrayal, and twisted justice, often with a tragic or ironic ending.",

    "philosophy": "- This is philosophy-focused. Explore deep questions and let philosophical ideas guide the narrative. The setting often challenges characters with existential dilemmas, ethical debates, and the search for meaning in a complex world, where abstract ideas and theoretical concepts become central to the story.",

    "pirates": "- This is a pirate setting. Plunder treasure, navigate treacherous waters, and live the life of a seafaring outlaw. The setting is filled with swashbuckling adventures, hidden islands, and legendary treasures, where the code of the pirate and the thrill of the high seas define the characters' lives and destinies.",

    "poetic_fantasy": "- This is poetic fantasy. Craft beautiful, lyrical prose set in a magical world of wonder. The setting emphasizes the beauty of language and the power of imagination, where every word is chosen for its musicality and resonance, creating a world that is as much about the experience of the narrative as it is about the plot.",

    "post_apocalyptic": "- This is a post-apocalyptic setting. Survive in a world after civilization has fallen, facing new dangers and harsh realities. The setting is marked by desolation, the remnants of a once-great society, and the struggle to rebuild or simply survive in a world where the old rules no longer apply.",

    "rats": "- This focuses on rats. Explore the world from the perspective of these small, resourceful creatures. The narrative often delves into the hidden corners of cities, the survival instincts of rats, and their complex social structures, as they navigate a world that is both familiar and alien to human eyes.",

    "roman_empire": "- This is set in the Roman Empire. Experience the glory, politics, and daily life of ancient Rome. The setting includes grand architecture, the might of the legions, and the intrigues of the Senate, where characters can rise to power, become embroiled in conspiracies, or witness the splendor and decay of Rome.",

    "science_fantasy": "- This is science fantasy. Blend advanced technology with magical elements in a world where science and sorcery coexist. The setting is a fusion of the scientific and the mystical, where spaceships and spellcasters share the same universe, and the laws of physics are intertwined with the arcane.",

    "space_opera": "- This is space opera. Feature grand adventures across the galaxy, alien species, and interstellar conflicts. The setting is vast and epic, with complex political landscapes, vast starships, and the struggles of empires and rebels in a universe where anything is possible and the stakes are galaxy-wide.",

    "superheroes": "- This is a superhero setting. Explore a world where individuals with extraordinary abilities fight for justice or villainy. The setting includes secret identities, epic battles, and the moral dilemmas that come with great power, where heroes and villains shape the fate of cities and nations.",

    "steampunk": "- This is a steampunk setting. Combine Victorian aesthetics with advanced steam-powered technology and clockwork inventions. The setting is rich with gears, cogs, and brass, where innovation and imagination fuel a world of airships, automatons, and anachronistic wonders, blending the old with the new.",

    "travel": "- This is travel-focused. Journey to exotic locations, experience diverse cultures, and embark on globe-spanning adventures. The setting emphasizes exploration, discovery, and the joys and challenges of traveling, whether it's a grand tour of the world's wonders or a personal quest across distant lands.",

    "urban_fantasy": "- This is urban fantasy. Integrate magical elements and creatures into a modern, urban setting. The setting blends the mundane with the magical, where hidden societies, supernatural beings, and enchanted places exist alongside the everyday, often unnoticed by the general public.",

    "valentines": "- This is Valentine's Day themed. Focus on romantic relationships, love stories, and matters of the heart. The setting is filled with love letters, romantic gestures, and the joys and challenges of relationships, often set against the backdrop of Valentine's Day celebrations, where love is in the air.",

    "vikings": "- This is a Viking setting. Feature Norse warriors, sea raids, and the harsh but exciting life in Scandinavian lands. The setting is rich with Norse mythology, the saga of heroism, and the spirit of exploration, where the call of the sea and the thrill of battle are central to the Viking way of life.",

    "weird_west": "- This is Weird West. Combine traditional Western elements with supernatural and magical aspects. The setting blends the rugged frontier of the American West with strange and otherworldly elements, where gunslingers might face off against ghosts, demons, and creatures of folklore in a landscape where anything can happen.",

    "western_romance": "- This is Western romance. Blend the rugged frontier life with passionate love stories. The setting combines the untamed wilderness, the challenges of life on the frontier, and the deep emotions of love and desire, often set against a backdrop of cowboys, ranches, and the open plains."
}


# Set the default theme here. Change this to apply a different theme.
DEFAULT_THEME = "dark_fantasy"


def get_next_api_url():
    global current_api_index, last_switch_time, request_count

    if switch_mode == "time":
        if time.time() - last_switch_time >= switch_interval:
            current_api_index = (current_api_index + 1) % len(api_urls)
            last_switch_time = time.time()
            logging.info(f"Switched API due to time interval. New API: {api_urls[current_api_index]}")
    elif switch_mode == "request":
        if request.path == '/v1/completions':  # Only count main generation requests
            request_count += 1
            if request_count >= delay_between_switches:
                current_api_index = (current_api_index + 1) % len(api_urls)
                request_count = 0
                logging.info(f"Switched API due to request count. New API: {api_urls[current_api_index]}")

    return api_urls[current_api_index]


def stream_response(response):
    for chunk in response.iter_content(chunk_size=1024):
        yield chunk


import re


@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def proxy(path):
    for attempt in range(max_retries):
        try:
            api_url = get_next_api_url()
            target_url = f"{api_url}/{path}"
            logging.info(f"Proxying request to: {target_url}")

            # Handle file uploads for audio transcriptions
            files = None
            if path == 'v1/audio/transcriptions' and request.method == 'POST':
                if 'file' not in request.files:
                    return Response("No file part in the request", status=400)
                file = request.files['file']
                files = {'file': (file.filename, file.stream, file.content_type)}

            # Process theme for completions request
            if request.method == 'POST' and path == 'v1/completions':
                data = request.get_json()

                if DEFAULT_THEME != "none" and DEFAULT_THEME in themes:
                    prompt = data['prompt']
                    theme_entry = f'"{DEFAULT_THEME}": "{themes[DEFAULT_THEME]}",\n'

                    # Split the prompt into lines
                    lines = prompt.split('\n')

                    # Find the insertion point (4 lines from the end)
                    insertion_point = max(0, len(lines) - 4)

                    # Insert the theme entry
                    lines.insert(insertion_point, theme_entry)

                    # Rejoin the lines
                    data['prompt'] = '\n'.join(lines)

                request_data = json.dumps(data)
            else:
                request_data = request.get_data()

            # Forward the request to the target API
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers={key: value for (key, value) in request.headers if key != 'Host'},
                data=request_data if not files else None,
                files=files,
                cookies=request.cookies,
                allow_redirects=False,
                timeout=request_timeout,
                stream=True
            )

            # Handle streaming responses
            if path == 'api/extra/generate/stream':
                return Response(stream_with_context(stream_response(resp)),
                                content_type=resp.headers.get('content-type'))

            # Create a Flask Response object from the API response
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if
                       name.lower() not in excluded_headers]
            response = Response(resp.content, resp.status_code, headers)
            return response

        except requests.RequestException as e:
            logging.error(f"Error connecting to {api_url}: {str(e)}")
            time.sleep(1)  # Wait for 1 second before retrying

    logging.error(f"Failed to proxy request after {max_retries} attempts")
    return Response("Failed to proxy request", status=500)


def switch_api_periodically():
    global current_api_index, last_switch_time
    while True:
        time.sleep(switch_interval)
        if switch_mode == "time":
            current_api_index = (current_api_index + 1) % len(api_urls)
            last_switch_time = time.time()
            logging.info(f"Periodically switched API. New API: {api_urls[current_api_index]}")


if __name__ == '__main__':
    logging.info("Starting Kobold API proxy")
    if switch_mode == "time":
        threading.Thread(target=switch_api_periodically, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=5066)