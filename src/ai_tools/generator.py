import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class DnDGenerator:
    def __init__(self, *, model: str | None = None):
        litellm_base_url = os.getenv("LITELLM_BASE_URL") or os.getenv("LITELLM_PROXY_URL")
        if litellm_base_url:
            # LiteLLM proxy is OpenAI-compatible.
            self.client = OpenAI(
                api_key=os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
                base_url=litellm_base_url.rstrip("/") + "/v1",
            )
            self.model = model or os.getenv("DND_DEFAULT_MODEL") or "gpt-5.2"
        else:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = model or os.getenv("DND_DEFAULT_MODEL") or "gpt-5.2"

    def generate_character_backstory(self, name, race, char_class):
        """Generate a backstory for a D&D character."""
        prompt = f"Write a short, compelling backstory for a D&D character named {name}, who is a {race} {char_class}."
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a creative Dungeon Master and storyteller."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    def generate_plot_hook(self, setting="a small village"):
        """Generate a plot hook for a D&D adventure."""
        prompt = f"Generate 3 unique and mysterious plot hooks for a D&D adventure starting in {setting}."
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a creative Dungeon Master."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

if __name__ == "__main__":
    # Example usage (requires OPENAI_API_KEY in .env)
    # gen = DnDGenerator()
    # print(gen.generate_character_backstory("Thokk", "Half-Orc", "Barbarian"))
    print("DnD Generator initialized. Set your OPENAI_API_KEY in .env to use.")
