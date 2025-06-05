from gtts import gTTS
import pygame
import tempfile
import os


def speak_alert():
    try:
        # Generate speech
        tts = gTTS(text="Please solve the captcha!", lang='en')

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            temp_file = f.name
            tts.save(temp_file)

        # Initialize pygame mixer
        pygame.mixer.init()
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Wait until playback finishes (fixed version)
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)  # Use pygame.time.Clock instead

        # Clean up
        pygame.mixer.quit()
        os.unlink(temp_file)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    pygame.init()  # Initialize pygame
    speak_alert()