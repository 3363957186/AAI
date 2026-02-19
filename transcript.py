from youtube_transcript_api import YouTubeTranscriptApi
import json
import re


def clean_transcript_text(text: str) -> str:
    """
    Clean transcript text:
    - Remove \n (YouTube subtitle line breaks)
    - Remove extra spaces
    - Fix punctuation spacing
    """
    # Replace \n with space
    text = text.replace('\n', ' ')

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Fix spacing around punctuation (optional)
    text = re.sub(r'\s+([.,!?])', r'\1', text)

    return text.strip()


def fetch_transcript_auto(video_id: str, debug: bool = True) -> dict:
    """
    Fetch transcript using correct API methods
    """
    if debug:
        print(f"\n  [DEBUG] Attempting to fetch transcript for video_id: {video_id}")

    try:
        if debug:
            print(f"  [DEBUG] Fetching transcript...")

        # Create an instance and fetch
        api = YouTubeTranscriptApi()
        transcript_obj = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])

        # Convert to list of dicts
        segments = []
        full_text_parts = []

        for seg in transcript_obj:
            # Clean the text to remove \n and extra spaces
            cleaned_text = clean_transcript_text(seg.text)

            segment_dict = {
                'text': cleaned_text,  # Use cleaned text
                'start': seg.start,
                'duration': seg.duration
            }
            segments.append(segment_dict)
            full_text_parts.append(cleaned_text)

        if debug:
            print(f"  [DEBUG] ✓ Got transcript with {len(segments)} segments")
            if len(segments) > 0:
                print(f"  [DEBUG] First 3 segments:")
                for i, seg in enumerate(segments[:3]):
                    print(f"    {i + 1}. [{seg['start']:.1f}s] {seg['text'][:60]}")

        full_text = " ".join(full_text_parts)

        return {
            "success": True,
            "transcript": full_text,
            "segments": segments,
            "language": "en",
            "error": None
        }

    except Exception as e:
        if debug:
            print(f"  [DEBUG] ✗ English transcript failed: {str(e)}")
            print(f"  [DEBUG] Strategy 2: Trying any available transcript...")

        try:
            # Try to fetch any available transcript (without language filter)
            api = YouTubeTranscriptApi()
            transcript_obj = api.fetch(video_id)

            # Convert to list of dicts
            segments = []
            full_text_parts = []

            for seg in transcript_obj:
                cleaned_text = clean_transcript_text(seg.text)

                segment_dict = {
                    'text': cleaned_text,
                    'start': seg.start,
                    'duration': seg.duration
                }
                segments.append(segment_dict)
                full_text_parts.append(cleaned_text)

            if debug:
                print(f"  [DEBUG] ✓ Got transcript with {len(segments)} segments")

            full_text = " ".join(full_text_parts)

            return {
                "success": True,
                "transcript": full_text,
                "segments": segments,
                "language": "auto-detected",
                "error": None
            }
        except Exception as e2:
            if debug:
                print(f"  [DEBUG] ✗ Failed to fetch any transcript: {str(e2)}")

    # If all failed
    return {
        "success": False,
        "transcript": None,
        "segments": None,
        "language": None,
        "error": "No transcript available for this video"
    }


def export_transcript(video_id: str, result: dict, output_dir: str = "comments"):
    """Export transcript to file"""
    import os

    os.makedirs(output_dir, exist_ok=True)

    if not result["success"]:
        print(f"  ⚠️  Cannot export transcript: {result['error']}")
        return

    # Export full text
    txt_path = os.path.join(output_dir, f"{video_id}_transcript.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Language: {result['language']}\n")
        f.write("=" * 60 + "\n\n")
        f.write(result['transcript'])

    print(f"  ✓ Transcript exported to {txt_path}")
    print(f"     Length: {len(result['transcript'])} characters")

    # Export timestamped segments
    json_path = os.path.join(output_dir, f"{video_id}_transcript_segments.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result['segments'], f, indent=2, ensure_ascii=False)

    print(f"  ✓ Segments exported to {json_path}")


def test_transcript(video_id: str):
    """Test function"""
    print("=" * 60)
    print(f"Testing transcript fetch for: {video_id}")
    print("=" * 60)

    result = fetch_transcript_auto(video_id, debug=True)

    print("\n" + "=" * 60)
    print("FINAL RESULT:")
    print("=" * 60)
    print(json.dumps({
        "success": result["success"],
        "language": result["language"],
        "error": result["error"],
        "transcript_length": len(result["transcript"]) if result["transcript"] else 0,
        "segments_count": len(result["segments"]) if result["segments"] else 0
    }, indent=2))

    if result["success"] and result["transcript"]:
        print("\nFirst 200 characters of transcript:")
        print(result["transcript"][:200] + "...")

    return result