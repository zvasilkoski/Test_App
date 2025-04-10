"""
    Gemini Testing App
    To Run: streamlit run app.py

"""

import streamlit as st
import pandas as pd
import re
import os
import io # Required for download button buffer
# Removed google.generativeai and dotenv as Gemini is not explicitly used in this version's core logic
# from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables (Optional - if needed for other purposes)
# load_dotenv()

# --- Constants ---
MCQ_FILE = "questions/Chapter_2_MC.md"
# Updated columns as per requirement
RESULTS_COLS = ["Question_ID", "Student_Answer", "Correct_Answer", "Points"]
USER_NAMES = ["Irena", "Ljube", "Zlatko"] # Allowed users

# --- Helper Functions ---

@st.cache_data # Cache the parsing result for efficiency
def parse_mcq_file(file_path):
    """Parses the MCQ markdown file."""
    questions = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        st.error(f"Error: Markdown file not found at '{file_path}'")
        return None
    except Exception as e:
        st.error(f"Error reading file '{file_path}': {e}")
        return None

    # Split into potential question blocks based on "Problem:"
    question_blocks = re.split(r'(?=^Problem:)', content, flags=re.MULTILINE)

    for block in question_blocks:
        block = block.strip()
        if not block:
            continue

        question_data = {}
        current_field = None
        value_buffer = []

        lines = block.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line and not current_field:
                continue

            match = re.match(r'^(Problem|Points|Type|Topic|Question|Answer|Explanation):(.*)', line)

            if match:
                if current_field and value_buffer:
                    question_data[current_field] = "\n".join(value_buffer).strip()
                current_field = match.group(1).strip()
                value_buffer = [match.group(2).strip()]
            elif current_field:
                value_buffer.append(line)

        if current_field and value_buffer:
            question_data[current_field] = "\n".join(value_buffer).strip()

        # --- Data Validation and Transformation ---
        if all(k in question_data for k in ["Problem", "Points", "Question", "Answer"]):
            try:
                # Rename 'Problem' to 'Question_ID' for clarity internally
                question_data['Question_ID'] = str(question_data.pop('Problem'))
                question_data['Points'] = int(float(question_data.get('Points', 0)))
            except ValueError:
                st.warning(f"Could not parse Points for Question ID {question_data.get('Question_ID', 'N/A')}. Setting points to 0.")
                question_data['Points'] = 0

            # --- Extract Options ---
            question_text_lines = []
            options_dict = {}
            option_pattern = re.compile(r'^([A-Z])\)\s*(.*)') # Supports A), B), C), D), E)...
            in_options_section = False
            if 'Question' in question_data:
                for q_line in question_data['Question'].split('\n'):
                    option_match = option_pattern.match(q_line)
                    if option_match:
                        in_options_section = True
                        option_letter = option_match.group(1)
                        option_text = option_match.group(2)
                        options_dict[option_letter] = option_text
                    elif not in_options_section:
                        question_text_lines.append(q_line)
                    elif in_options_section and q_line.strip():
                         last_letter = list(options_dict.keys())[-1] if options_dict else None
                         if last_letter:
                             options_dict[last_letter] += "\n" + q_line

            question_data['Question_Text'] = "\n".join(question_text_lines).strip()
            question_data['Options'] = options_dict

            # Validate Answer format and existence
            if 'Answer' in question_data:
                 correct_letter = question_data['Answer'].strip().upper()
                 question_data['Answer'] = correct_letter # Store the cleaned answer
                 if correct_letter not in question_data['Options']:
                      st.warning(f"Question ID {question_data['Question_ID']}: Correct answer '{correct_letter}' not found as an option key ({list(question_data['Options'].keys())}). Check MD file format.")

            questions.append(question_data)
        else:
            st.warning(f"Skipping incomplete question block (missing required fields): {block[:100]}...")

    if not questions:
         st.error("No valid questions parsed from the file.")
         return None

    # Sort questions based on Question_ID assuming it's numeric or can be compared
    try:
        questions.sort(key=lambda q: int(q['Question_ID']))
    except ValueError:
        st.warning("Could not sort questions numerically by ID. Using original order.")


    return questions


# --- Main App ---
st.set_page_config(page_title="MCQ Quiz", page_icon="./images/BU_Logo.png", layout="wide")
st.title("📚 Multiple Choice Quiz")

# --- Initialize Session State ---
# Core App State
if 'quiz_started' not in st.session_state:
    st.session_state.quiz_started = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'current_question_index' not in st.session_state:
    st.session_state.current_question_index = 0
if 'results' not in st.session_state:
    st.session_state.results = pd.DataFrame(columns=RESULTS_COLS)
if 'questions' not in st.session_state:
    st.session_state.questions = parse_mcq_file(MCQ_FILE)
if 'quiz_finished' not in st.session_state: # More specific than show_results_page
    st.session_state.quiz_finished = False

# State for individual question interaction
if 'answer_submitted' not in st.session_state:
     # Tracks if the *current* question's answer has been submitted
    st.session_state.answer_submitted = False
if 'current_feedback' not in st.session_state:
    # Stores feedback ("Correct", "Incorrect Answer") for the *current* question after submission
    st.session_state.current_feedback = None
if 'selected_answer' not in st.session_state:
    # Stores the user's selection for the radio button *before* submission
    st.session_state.selected_answer = None



# --- Sidebar ---
with st.sidebar:
    st.image("images/BU_Logo_new.png", width=150, use_container_width=True)
    st.header("User Selection")
    # Disable selectbox if quiz has started
    username = st.selectbox(
        "Select User:",
        options=[""] + USER_NAMES, # Add empty option for default
        index=0, # Default to empty
        key='user_select',
        disabled=st.session_state.quiz_started
    )

    # Show Start button only if a user is selected AND quiz hasn't started
    if username and not st.session_state.quiz_started:
        if st.button("Start Test"):
            st.session_state.user_name = username
            st.session_state.quiz_started = True
            # Reset quiz state if starting fresh for a user
            st.session_state.current_question_index = 0
            st.session_state.results = pd.DataFrame(columns=RESULTS_COLS)
            st.session_state.quiz_finished = False
            st.session_state.answer_submitted = False
            st.session_state.current_feedback = None
            st.session_state.selected_answer = None
            st.rerun() # Rerun to update UI based on quiz_started state
    elif st.session_state.quiz_started:
        st.success(f"Quiz started for: {st.session_state.user_name}")


# --- Main Panel Logic ---
if st.session_state.quiz_started:

    if not st.session_state.questions:
        st.error("Failed to load questions. Cannot proceed.")
        st.stop()

    total_questions = len(st.session_state.questions)

    # Check if quiz is finished
    if st.session_state.current_question_index >= total_questions:
        st.session_state.quiz_finished = True

    # --- Quiz Question Display ---
    if not st.session_state.quiz_finished:
        st.header(f"Question {st.session_state.current_question_index + 1} of {total_questions}")
        st.divider()

        current_q_data = st.session_state.questions[st.session_state.current_question_index]
        question_id = current_q_data.get('Question_ID', f"Unknown_{st.session_state.current_question_index+1}")
        points = current_q_data.get('Points', 0)
        q_type = current_q_data.get('Type', 'N/A')
        topic = current_q_data.get('Topic', 'N/A')
        question_text = current_q_data.get('Question_Text', 'Error: Question text missing.')
        options = current_q_data.get('Options', {})
        correct_answer_letter = current_q_data.get('Answer', '') # Already cleaned in parser
        explanation_md = current_q_data.get('Explanation', 'No explanation provided.')

        # Display Question Info
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Points:** {points}")
            st.info(f"**Type:** {q_type}")
        with col2:
             st.info(f"**Topic:** {topic}")

        st.markdown("**Question:**")
        st.markdown(question_text, unsafe_allow_html=True)
        st.divider()

        if not options:
            st.error("Error: No options found for this question. Check the Markdown file.")
            # Simple skip for now, could add more robust handling
            if st.button("Skip Malformed Question"):
                 # Record skipped question with 0 points
                 new_row = pd.DataFrame([{
                     "Question_ID": question_id,
                     "Student_Answer": "SKIPPED (No Options)",
                     "Correct_Answer": correct_answer_letter,
                     "Points": 0
                 }])
                 st.session_state.results = pd.concat([st.session_state.results, new_row], ignore_index=True)
                 st.session_state.current_question_index += 1
                 st.session_state.answer_submitted = False # Reset for next potential question
                 st.session_state.current_feedback = None
                 st.session_state.selected_answer = None
                 st.rerun()

        else:
            # --- Answer Section ---
            option_keys = list(options.keys())

            # Display Radio buttons if answer not yet submitted
            if not st.session_state.answer_submitted:
                # Use st.radio and store its state temporarily
                # The key ensures the selection persists during reruns before submission
                st.session_state.selected_answer = st.radio(
                    "Choose your answer:",
                    options=option_keys,
                    format_func=lambda key: f"{key}) {options[key]}",
                    key=f"q_radio_{st.session_state.current_question_index}",
                    index=None # Default to no selection
                )

                # Show Submit button
                submit_button = st.button("Submit Answer", key=f"submit_{st.session_state.current_question_index}", disabled=(st.session_state.selected_answer is None))

                if submit_button and st.session_state.selected_answer is not None:
                    user_answer = st.session_state.selected_answer
                    points_earned = 0
                    feedback = ""

                    # Grade the answer
                    if user_answer == correct_answer_letter:
                        points_earned = points
                        feedback = "Correct"
                        st.success("Correct!")
                    else:
                        points_earned = 0
                        feedback = "Incorrect Answer"
                        st.error("Incorrect Answer")

                    # Store the result
                    new_row = pd.DataFrame([{
                        "Question_ID": question_id,
                        "Student_Answer": user_answer,
                        "Correct_Answer": correct_answer_letter,
                        "Points": points_earned
                    }])
                    st.session_state.results = pd.concat([st.session_state.results, new_row], ignore_index=True)

                    # Update state to show feedback and Next button
                    st.session_state.answer_submitted = True
                    st.session_state.current_feedback = feedback
                    st.rerun() # Rerun to display feedback and Next button

            # Show Feedback and Explanation if answer HAS been submitted
            elif st.session_state.answer_submitted:
                # Re-display feedback message (persists after rerun)
                if st.session_state.current_feedback == "Correct":
                    st.success("Correct!")
                elif st.session_state.current_feedback == "Incorrect Answer":
                    st.error("Incorrect Answer")
                else: # Should not happen, but good practice
                    st.warning("Feedback state unclear.")


                # Display Correct Answer and Explanation
                st.markdown(f"**Correct Answer:** {correct_answer_letter}) {options.get(correct_answer_letter, 'N/A')}")
                with st.expander("Explanation", expanded=True):
                     st.markdown(explanation_md if explanation_md else "No explanation provided in the file.")

                st.divider()

                # Show Next Question button if not the last question
                if st.session_state.current_question_index < total_questions - 1:
                    if st.button("Next Question", key=f"next_{st.session_state.current_question_index}"):
                        st.session_state.current_question_index += 1
                        # Reset state for the upcoming question
                        st.session_state.answer_submitted = False
                        st.session_state.current_feedback = None
                        st.session_state.selected_answer = None # Clear selection for next radio
                        st.rerun()
                else:
                    # This was the last question, mark quiz as finished
                    # No "Next Question" button shown
                     if not st.session_state.quiz_finished:
                          st.session_state.quiz_finished = True
                          st.rerun() # Rerun to trigger the results page display


    # --- Results Page Display ---
    elif st.session_state.quiz_finished:
        st.balloons()
        st.header("🏁 Quiz Finished! 🏁")
        st.subheader(f"Results for: {st.session_state.user_name}")

        results_df = st.session_state.results

        if not results_df.empty:
            # Calculate Score
            total_points_earned = results_df['Points'].sum()
            # Calculate max possible points by summing points for all questions attempted
            # Need to fetch max points for each question ID present in results
            max_points_possible = 0
            attempted_ids = results_df['Question_ID'].unique()
            for q_id in attempted_ids:
                 q_data = next((q for q in st.session_state.questions if q['Question_ID'] == str(q_id)), None)
                 if q_data:
                      max_points_possible += q_data.get('Points', 0)


            # Calculate percentage
            score_percent = (total_points_earned / max_points_possible * 100) if max_points_possible > 0 else 0

            st.metric("Final Score", f"{total_points_earned} / {max_points_possible}", f"{score_percent:.2f}% Correct")
            st.divider()

            # Save Results Button
            st.subheader("Save Your Results")

            # Sanitize filename
            safe_username = "".join(c if c.isalnum() else "_" for c in st.session_state.user_name)
            csv_filename = f"{safe_username}_results.csv"

            # Convert DataFrame to CSV string/bytes
            csv_buffer = io.StringIO()
            results_df.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_data = csv_buffer.getvalue()

            st.download_button(
                label="💾 Save Results",
                data=csv_data,
                file_name=csv_filename,
                mime='text/csv',
                key='download_results'
            )
            st.info(f"Click the button above to download your results as '{csv_filename}'.")

        else:
            st.warning("No results recorded for this session.")

        st.divider()
        # Optional: Add a button to start over or select a different user
        if st.button("Start New Quiz (Different User)"):
             # Reset all relevant state
             st.session_state.quiz_started = False
             st.session_state.user_name = None
             st.session_state.current_question_index = 0
             st.session_state.results = pd.DataFrame(columns=RESULTS_COLS)
             st.session_state.quiz_finished = False
             st.session_state.answer_submitted = False
             st.session_state.current_feedback = None
             st.session_state.selected_answer = None
             # Clear the user selection widget state too if needed
             st.session_state.user_select = "" # Reset selectbox
             st.rerun()


# --- Initial State (Before Quiz Starts) ---
elif not st.session_state.quiz_started:
    st.info("⬅️ Please select a user from the sidebar and click 'Start Test'.")

