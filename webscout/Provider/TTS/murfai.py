import time
import requests
import pathlib
from io import BytesIO
from urllib.parse import urlencode
from playsound import playsound
from nltk import sent_tokenize
from webscout import exceptions
from webscout.AIbase import TTSProvider
from concurrent.futures import ThreadPoolExecutor, as_completed

class MurfAITTS(TTSProvider):
    """Text-to-speech provider using the MurfAITTS API."""
    # Request headers
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    cache_dir = pathlib.Path("./audio_cache")
    all_voices: dict[str, str] = {"Hazel": "en-UK-hazel"}

    def __init__(self, timeout: int = 20, proxies: dict = None):
        """Initializes the MurfAITTS TTS client."""
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        if proxies:
            self.session.proxies.update(proxies)
        self.timeout = timeout

    def tts(self, text: str, voice: str = "Hazel", verbose:bool = True) -> str:
        """Converts text to speech using the MurfAITTS API and saves it to a file."""
        assert (
            voice in self.all_voices
        ), f"Voice '{voice}' not one of [{', '.join(self.all_voices.keys())}]"

        filename = self.cache_dir / f"{int(time.time())}.mp3"

        voice_id = self.all_voices[voice]

        # Split text into sentences
        sentences = sent_tokenize(text)

        # Function to request audio for each chunk
        def generate_audio_for_chunk(part_text: str, part_number: int):
            while True:
                try:
                    params: dict[str, str] = {
                    "name": voice_id, 
                    "text": part_text
                    }
                    encode_param: str = urlencode(params)
                    response = self.session.get(f"https://murf.ai/Prod/anonymous-tts/audio?{encode_param}", headers=self.headers, timeout=self.timeout)
                    response.raise_for_status()

                    # Create the audio_cache directory if it doesn't exist
                    self.cache_dir.mkdir(parents=True, exist_ok=True) 

                    # Check if the request was successful
                    if response.ok and response.status_code == 200:
                        if verbose:print(f"Chunk {part_number} processed successfully.")
                        return part_number, response.content
                    else:
                        if verbose:
                            print(f"No data received for chunk {part_number}. Retrying...")
                except requests.RequestException as e:
                    # if verbose:
                    #     print(f"Error for chunk {part_number}: {e}. Retrying...")
                    time.sleep(1)
        try:
            # Using ThreadPoolExecutor to handle requests concurrently
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(generate_audio_for_chunk, sentence.strip(), chunk_num): chunk_num 
                        for chunk_num, sentence in enumerate(sentences, start=1)}
                
                # Dictionary to store results with order preserved
                audio_chunks = {}

                for future in as_completed(futures):
                    chunk_num = futures[future]
                    try:
                        part_number, audio_data = future.result()
                        audio_chunks[part_number] = audio_data  # Store the audio data in correct sequence
                    except Exception as e:
                        if verbose:
                            print(f"Failed to generate audio for chunk {chunk_num}: {e}")

            # Combine audio chunks in the correct sequence
            combined_audio = BytesIO()
            for part_number in sorted(audio_chunks.keys()):
                combined_audio.write(audio_chunks[part_number])
                if verbose:
                    print(f"Added chunk {part_number} to the combined file.")

            # Save the combined audio data to a single file
            with open(filename, 'wb') as f:
                f.write(combined_audio.getvalue())
            if verbose:print(f"\033[1;93mFinal Audio Saved as {filename}.\033[0m")
            return filename.as_posix()

        except requests.exceptions.RequestException as e:
            raise exceptions.FailedToGenerateResponseError(
                f"Failed to perform the operation: {e}"
            )
        
    def play_audio(self, filename: str):
        """
        Plays an audio file using playsound.

        Args:
            filename (str): The path to the audio file.

        Raises:
            RuntimeError: If there is an error playing the audio.
        """
        try:
            playsound(filename)
        except Exception as e:
            raise RuntimeError(f"Error playing audio: {e}")

# Example usage
if __name__ == "__main__":
    elevenlabs = MurfAITTS()
    text = "This is a test of the MurfAITTS text-to-speech API."

    print("Generating audio...")
    audio_file = elevenlabs.tts(text, voice="Brian") 

    print("Playing audio...")
    audio_file.play_audio(audio_file)