import os
import random
import shutil
from typing import Optional

from fastapi import FastAPI

import user
from generate import generate_screen
from levels import question_levels

app = FastAPI()

default_instrument = user.instrument
user_progress = user.level_progress
default_language = user.lang


def get_user_level_details(user_level):
    # Get the first letter of the user level
    book = user_level[0]

    # Get the rest of the user level
    lesson_id = user_level[1:]

    # Create a dictionary to map letters to book names
    book_map = {"T": "theory", "R": "rhythm", "L": "listen"}

    # Use the dictionary to get the book name
    book = book_map[book]

    # Return the book and the lesson ID
    return book, lesson_id


def generate_question_list(user_level, number_of_questions):
    # Create a dictionary to hold the questions
    lesson_list = []

    # Create a while loop to generate questions until the number of questions matches the input
    question_count = 1
    while len(lesson_list) < number_of_questions:
        # Generate a random user level if the input is a list of levels (a.k.a practice mode)
        if isinstance(user_level, list):
            user_level = random.choice(user_level)

        # Get the book and lesson ID from the user level
        book, lesson_id = get_user_level_details(user_level)

        # Get the chapter and lesson from the lesson ID
        chapter, lesson = int(lesson_id[0]), int(lesson_id[-1])
        # Get the question type and answer type from the lesson choices
        lessons = question_levels[default_instrument][book][chapter]["lessons"][lesson]
        question_type = random.choice(list(lessons["question choices"].keys()))
        answer_type = random.choice(list(lessons["question choices"][question_type].keys()))

        # Generate the screen to be displayed to the user
        screen = generate_screen(question_type, answer_type, user_level, default_language)
        # Unpack the screen into its components
        question, answer = screen

        # Add the question to the lesson list
        question_dict = {                
            "id": question_count,
            "name": "Question " + str(question_count),
            "type": "question",
            "question": question,
            "answer": answer
        }

        lesson_list.append(question_dict)
        question_count += 1

    # Return the question dictionary
    return lesson_list


def clear_folders(*folders):
    for folder in folders:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")


@app.get("/")
async def root():
    return {"message": "welcome to my API :)"}


@app.get("/cleanup")  # change to POST if needed
async def cleanup():
    # Path to the directory where the code is currently running
    base_path = os.path.dirname(os.path.abspath(__file__))

    # Path to the folder containing the midi files
    midi_files_path = os.path.join(base_path, "midi_files")

    # Path to the folder containing the wav files
    wav_files_path = os.path.join(base_path, "wav_files")

    # Path to the folder containing the xml files
    xml_files_path = os.path.join(base_path, "xml_files")

    # Delete all files in each folder
    clear_folders(midi_files_path, wav_files_path, xml_files_path)

    # Return a JSON object containing the status message
    return {"status": "folders cleared"}


@app.get("/user")
async def user_details():
    # Return the user details
    return {"instrument": default_instrument, "user progress": user_progress, "user language": default_language}


@app.get("/practice")
async def practice_details():
    # Returns the user progress
    return {"user progress": user_progress}


@app.get("/practice/generate")
async def generate_practice(q: Optional[int] = None):
    """Generate a list of practice questions.

    Args:
        q: Optional number of questions to generate. If not provided, this
           will default to 20.

    Returns:
        A list of practice questions.
    """
    number_of_questions = q or 20
    return generate_question_list(user_progress, number_of_questions)


@app.get("/{book}")
async def book_details(book: str, chapter: Optional[int] = None):
    # check if the book is valid and return an error if not
    if book not in ["theory", "listen", "rhythm"]:
        return {"Error": "Not a valid book type"}

    # if a chapter is specified, return details about that chapter
    if chapter:
        chapter_details = question_levels[default_instrument][book][chapter]
        lesson_names = [lesson["lesson name"] for lesson in chapter_details["lessons"].values()]
        return {"number": chapter, "name": chapter_details["chapter name"], "lesson names": lesson_names}

    # otherwise, return details about all chapters
    output_dict = {}
    for chapter_num, chapter_details in question_levels[default_instrument][book].items():
        lesson_length = len(chapter_details["lessons"])
        lesson_names = [lesson["lesson name"] for lesson in chapter_details["lessons"].values()]
        output_dict[chapter_num] = {"number": chapter_num, "name": chapter_details["chapter name"], "length": lesson_length, "lesson names": lesson_names}

    return output_dict


@app.get("/{book}/{lesson_id}")
async def lesson_details(book: str, lesson_id: str):
    """
    Get the details for a specific lesson.

    Parameters
    ----------
    book : str
        The type of book to get the lesson from. Must be one of
        ["theory", "listen", "rhythm"].
    lesson_id : str
        The id of the lesson to get. Must be a string with the chapter
        number as the first character and the lesson number as the
        second character. For example, "1A" or "3B".

    Returns
    -------
    dict
        The details for the requested lesson. If the lesson does not
        exist, then the dictionary will only contain the key "Error".
    """
    # Check that the book type is valid
    if book not in ["theory", "listen", "rhythm"]:
        return {"Error": "Not a valid book type"}

    # Get the chapter and lesson numbers
    chapter, lesson = int(lesson_id[0]), int(lesson_id[-1])

    # Check that the chapter number is valid
    if chapter not in question_levels[default_instrument][book]:
        return {"Error": "Not a valid chapter number"}

    # Check that the lesson number is valid
    if lesson not in question_levels[default_instrument][book][chapter]["lessons"]:
        return {"Error": "Not a valid lesson number"}

    # Return the lesson details
    return question_levels[default_instrument][book][chapter]["lessons"][lesson]


@app.get("/{book}/{lesson_id}/generate")
async def generate_lesson(book: str, lesson_id: str):
    """"
    Generate a list of questions for a specific lesson. 
    """
    # Check that the book type is valid
    if book not in ["theory", "listen", "rhythm"]:
        return {"Error": "Not a valid book type"}

    # Split the lesson ID into chapter and lesson number
    chapter, lesson = int(lesson_id[0]), int(lesson_id[-1])

    # Check that the chapter number is valid
    if chapter not in question_levels[default_instrument][book]:
        return {"Error": "Not a valid chapter number"}

    # Check that the lesson number is valid
    if lesson not in question_levels[default_instrument][book][chapter]["lessons"]:
        return {"Error": "Not a valid lesson number"}

    # Generate a list of 20 questions
    number_of_questions = 20
    user_level = book[0].upper() + lesson_id

    return generate_question_list(user_level, number_of_questions)
