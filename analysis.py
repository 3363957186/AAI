import os
import glob
import json
import google.generativeai as genai
from pydantic import BaseModel, Field

# 1. Define the exact structure we want the AI to return
class ProductSummary(BaseModel):
    executive_overview: str
    key_features: list[str]
    pros: list[str]
    cons: list[str]
    overall_sentiment: str = Field(description="Must be 'Positive', 'Negative', or 'Mixed'")
    product_score: int = Field(description="An integer from 1 to 100")

# 2. Configure the Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set the GEMINI_API_KEY environment variable.")

genai.configure(api_key=api_key)

def summarize_product_transcripts(keyword: str, directory: str = "."):
    """
    Fetches all *_transcript.txt files, uses Gemini to generate a summary,
    and returns the structured data including an integer score.
    """

    search_pattern = os.path.join(directory, "*_transcript.txt")
    transcript_files = glob.glob(search_pattern)

    if not transcript_files:
        print(f"No files ending with '_transcript.txt' were found in {directory}.")
        return None

    print(f"Found {len(transcript_files)} transcript(s). Reading files...")

    combined_transcripts = ""
    for file_path in transcript_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                combined_transcripts += f"\n\n--- Transcript from {os.path.basename(file_path)} ---\n\n"
                combined_transcripts += file.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # 3. Construct the prompt
    # Since the structure is handled by Pydantic, the prompt just needs context and the rubric
    prompt = f"""
    You are an expert product analyst. Below are transcripts from multiple videos 
    discussing a product called '{keyword}'. 
    
    Please read through all of these transcripts and extract the required information.
    For the 'executive_overview', limit the word count to within 100 words.
    For the 'product_score', use this scale based on the transcripts: 
    1-20 = Terrible, 21-40 = Poor, 41-60 = Average, 61-80 = Good, 81-100 = Excellent.

    Here are the transcripts:
    {combined_transcripts}
    """

    print(f"Sending transcripts to Gemini for product: {keyword}...")
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')

        # 4. Pass the Pydantic schema to the generation config
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ProductSummary,
            ),
        )

        # 5. Parse the JSON string returned by Gemini into a Python dictionary
        summary_dict = json.loads(response.text)

        # 6. Extract the numeric score as an integer variable!
        final_score_int = summary_dict["product_score"]

        print("\n=== EXTRACTION SUCCESSFUL ===\n")
        print(f"Overview: {summary_dict['executive_overview']}")
        print(f"Sentiment: {summary_dict['overall_sentiment']}")
        print(f"\nThe integer score variable is: {final_score_int} (Type: {type(final_score_int)})")

        # You can now return or use final_score_int however you need
        return summary_dict

    except Exception as e:
        print(f"An error occurred while communicating with the Gemini API: {e}")
        return None

def analyze_sentiment_data(directory: str = "."):
    # Initialize our tracking variables
    positive_weighted_sum = 0.0
    negative_weighted_sum = 0.0
    total_sentiment_score = 0.0
    total_comments = 0

    # 1. Fetch all files ending with '_clean.txt'
    search_pattern = os.path.join(directory, '*_clean.txt')
    file_paths = glob.glob(search_pattern)

    if not file_paths:
        print(f"No files matching '*_clean.txt' found in {directory}.")
        return

    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                raw_content = file.read().strip()

                # Handle potential trailing commas or missing array brackets
                # (common if dictionaries are just dumped to a text file sequentially)
                if raw_content.startswith('{') and raw_content.endswith(','):
                    raw_content = '[' + raw_content[:-1] + ']'
                elif raw_content.startswith('{') and raw_content.endswith('}'):
                    raw_content = '[' + raw_content + ']'

                # Remove any trailing comma right before a closing bracket (invalid JSON)
                raw_content = raw_content.replace(',]', ']').replace(', \n]', '\n]')

                # Parse the JSON data
                comments = json.loads(raw_content)

                # Ensure we are iterating over a list
                if isinstance(comments, dict):
                    comments = [comments]

                # 2. Process each comment
                for comment in comments:
                    like_count = comment.get("like_count", 0)
                    sentiment_score = comment.get("sentiment_score", 0.0)
                    sentiment_label = comment.get("sentiment_label", "")

                    # Calculate the required variable: (1 + 0.05 * like_count) * sentiment_score
                    weighted_score = (1 + 0.05 * like_count) * sentiment_score

                    # 3. Sum the variables for positive vs negative
                    if sentiment_label == "positive":
                        positive_weighted_sum += weighted_score
                    elif sentiment_label == "negative":
                        negative_weighted_sum += weighted_score

                    # Accumulate total sentiment score for the average
                    total_sentiment_score += sentiment_score
                    total_comments += 1

        except json.JSONDecodeError as e:
            print(f"Skipping {os.path.basename(file_path)}: Invalid JSON format. Error: {e}")
        except Exception as e:
            print(f"Error processing {os.path.basename(file_path)}: {e}")

    # 4. Calculate the average sentiment score
    average_sentiment = total_sentiment_score / total_comments if total_comments > 0 else 0.0
    positive_percentage = positive_weighted_sum / (positive_weighted_sum + negative_weighted_sum)

    # Output the results
    print("--- Analysis Results ---")
    print(f"Total files processed: {len(file_paths)}")
    print(f"Total comments processed: {total_comments}")
    print(f"Sum of weighted variables (Positive): {positive_weighted_sum:.4f}")
    print(f"Sum of weighted variables (Negative): {negative_weighted_sum:.4f}")
    print(f"Average sentiment score: {average_sentiment:.4f}")
    print(f"Positive percentage: {positive_percentage:.4f}")
    print("------------------------")

# Example usage:
# Replace './data_folder' with the actual path to your directory
analyze_sentiment_data('./data_folder')
# --- Example Usage ---
if __name__ == "__main__":
    product_keyword = "Your Product Name"
    result = summarize_product_transcripts(keyword=product_keyword)

    # Example of using the int variable outside the function:
    if result:
        score = result["product_score"]
        if score > 80:
            print(f"\nLogic trigger: Wow! {product_keyword} got a great score of {score}!")