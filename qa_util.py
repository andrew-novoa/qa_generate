import base64
import math
import os
import random
import re
import tempfile

from midi2audio import FluidSynth
from music21 import (chord, clef, harmony, interval, key, meter, musicxml,
                     note, roman, scale, stream)
from pianoplayer.core import apply_fingerings

import user
from levels import content_levels
from theory import *

### Set Clef ###
user_instrument = user.instrument
if user_instrument == "bass":
    user_clef = clef.BassClef()
else:
    user_clef = clef.TrebleClef()

function_defaults = {
    "note":[None, None, False],
    "chord":[[], [], True],
    "chord progression":[None, False, None, "written"],
    "interval":[None, [], None, True],
    "scale":[[], [], None],
    "excerpt":[None, False, None],
    "rhythm":[[], [], None, 0.25],
    "arpeggio":[None, None, None],
    "note value":[[], None],
    "time elements":[[], []]
    }

def call_question_function(function_string, input_user_level, content_override=None):
    # If content_override is None, set it to an empty dictionary
    if content_override is None:
        content_override = {}

    # Create a dictionary book_map that maps input_user_level[0] to a string
    # (either "theory", "rhythm", or "listen")
    book_map = {"T": "theory", "R": "rhythm", "L": "listen"}
    book = book_map[input_user_level[0]]

    # Set admin_content to the content_levels dictionary value for the user's
    # instrument, the book, and the input_user_level
    admin_content = content_levels[user.instrument][book][input_user_level]
    # Create an empty dictionary function_fills
    function_fills = {}

    # Loop through the default values for the function_string
    for i in range(len(function_defaults[function_string])):
        # If there is a content_override and the i value is in the content_override
        # dictionary, set the function_fills dictionary value for i to the
        # content_override dictionary value for i
        if content_override and str(i) in content_override:
            function_fills[i] = content_override[str(i)]
        # If there is an admin_content value and the i value is in the
        # admin_content["generate " + function_string] dictionary, set the
        # function_fills dictionary value for i to the
        # admin_content["generate " + function_string] dictionary value for i
        elif admin_content and str(i) in admin_content["generate " + function_string]:
            function_fills[i] = admin_content["generate " + function_string][str(i)]
        # If neither of the above are true, set the function_fills dictionary
        # value for i to the function_defaults dictionary value for
        # function_string and i
        else:
            function_fills[i] = function_defaults[function_string][i]

    # Create a dictionary function_map that maps function_string to a function
    function_map = {
        "note": generate_note,
        "chord": generate_chord,
        "chord progression": generate_chord_progression,
        "interval": generate_interval,
        "scale": generate_scale,
        "excerpt": generate_excerpt,
        "rhythm": generate_rhythm,
        "arpeggio": generate_arpeggio,
        "note value": generate_note_value
    }

    # If function_string is in the function_map dictionary, return the function_map
    # dictionary value for function_string with the values in function_fills as
    # arguments
    if function_string in function_map:
        return function_map[function_string](*[function_fills[i] for i in range(len(function_defaults[function_string]))])
    # If the function_string is not in the function_map dictionary, raise a
    # ValueError with the function_string as a string
    else:
        raise ValueError(f"Unknown function_string: {function_string}")

### Main Functions ###

def generate_note(specific_note = None, specific_duration = None, stand_alone = False):
    new_note = note.Note()
    if specific_note != None:
        if type(specific_note) == list:
            new_note.pitch = random.choice(specific_note)
        else:
            new_note.pitch = specific_note
    else:
        new_note.pitch.midi = random.randrange(57, 73, 1) #range will depend on clef and user level

    if stand_alone == True:
        if specific_duration != None:
            new_note.duration.quarterLength = specific_duration
        else:
            duration_choices = [1, 2, 4]
            new_note.duration.quarterLength = random.choice(duration_choices)
        new_measure = stream.Measure(new_note)
        new_stream = stream.Stream()

        new_stream.append(user_clef)
        new_stream.append(new_measure)

        return new_stream
    
    else:
        return new_note

def generate_chord(chord_root_list = [], chord_quality_list = [], stand_alone = False): #figure out voicings and inversions
    
    if len(chord_root_list) != 0:
        random_root = random.choice(chord_root_list)
        root_note = note.Note(random_root + "4") if type(random_root) == str else note.Note(random_root)
    else:
        root_note = note.Note()
        root_note.pitch.midi = random.randrange(57, 73, 1)
    new_chord = chord.Chord()
    new_chord.add(root_note)

    if len(chord_quality_list) != 0:
        chord_quality = random.choice(chord_quality_list)
        for i in chord_by_interval_dict[chord_quality]:
            temp_interval = interval.Interval(i)
            temp_interval.pitchStart = root_note.pitch
            new_chord.add(temp_interval.pitchEnd)
    else:
        for i in chord_by_interval_dict[chord_interval_list[random.randrange(0, len(chord_interval_list), 1)]]:
            temp_interval = interval.Interval(i)
            temp_interval.pitchStart = root_note.pitch
            new_chord.add(temp_interval.pitchEnd)

    new_chord = fix_chord_spelling(new_chord)

    if stand_alone == True:
        duration_choices = [1, 2, 4]
        new_chord.duration.quarterLength = random.choice(duration_choices)
        new_stream = stream.Stream()
        new_measure = stream.Measure(new_chord)
        new_stream.append(new_measure)
        new_stream.timeSignature = None
        return new_stream
    else:
        return new_chord

def generate_chord_progression(input_key_sig = [], diatonic = True, score_length = None, output_type = "written", input_time_sig = [[], []], max_num_extensions = 1, min_division_level = 3):

    def calculate_divisions(meter_sequence, meter_division_count, min_division_level = 3):
        div_list = []
        prime_numbers = [3, 5, 7, 11, 13, 17]

        def get_duration(division):
            return (int(division[0]) / int(division[2])) * 4

        full_measure_duration = sum(get_duration(div) for div in meter_sequence)

        if meter_division_count == 2 and min_division_level > 1:
            first_half_duration = get_duration(meter_sequence[0])
            second_half_duration = get_duration(meter_sequence[1])

            # Ensuring that the sum of durations in the divisions does not exceed the full measure duration
            if first_half_duration + second_half_duration <= full_measure_duration:
                div_list.extend([[first_half_duration, second_half_duration], [first_half_duration, second_half_duration]])

            if int(meter_sequence[0][0]) in prime_numbers or int(meter_sequence[1][0]) in prime_numbers and min_division_level > 2:
                durations = [math.ceil(int(div[0]) / 2) for div in meter_sequence]
                quarter_lengths = [(duration / int(meter_sequence[0][2])) * 4 for duration in durations]

                # Same check applied here
                if sum(quarter_lengths) <= full_measure_duration:
                    div_list.extend([[quarter_lengths[0], quarter_lengths[1]], [quarter_lengths[0], quarter_lengths[1]]])

        elif meter_division_count == 3 and min_division_level > 1:
            third_durations = [get_duration(div) for div in meter_sequence]
            first_half_duration = third_durations[0] + third_durations[1]
            second_half_duration = third_durations[1] + third_durations[2]

            # Similar checks applied here
            if first_half_duration + second_half_duration <= full_measure_duration:
                div_list.extend([[first_half_duration, second_half_duration], [first_half_duration, second_half_duration]])

            if min_division_level > 2:
                if third_durations[0] + second_half_duration <= full_measure_duration:
                    div_list.append([third_durations[0], second_half_duration])

                if first_half_duration + third_durations[2] <= full_measure_duration:
                    div_list.append([first_half_duration, third_durations[2]])

                if sum(third_durations) <= full_measure_duration:
                    div_list.append(third_durations)

        elif meter_division_count == 4 and min_division_level > 1:
            quarter_lengths = [get_duration(div) for div in meter_sequence]
            first_half_duration = quarter_lengths[0] + quarter_lengths[1]
            second_half_duration = quarter_lengths[2] + quarter_lengths[3]

            # Similar checks applied here as well
            if min_division_level > 2:
                if first_half_duration + second_half_duration <= full_measure_duration:
                    div_list.extend([[first_half_duration, second_half_duration], [first_half_duration, second_half_duration]])

                if quarter_lengths[0] + quarter_lengths[1] + second_half_duration <= full_measure_duration:
                    div_list.append([quarter_lengths[0], quarter_lengths[1], second_half_duration])

                if first_half_duration + quarter_lengths[2] + quarter_lengths[3] <= full_measure_duration:
                    div_list.append([first_half_duration, quarter_lengths[2], quarter_lengths[3]])

                if sum(quarter_lengths) <= full_measure_duration:
                    div_list.append(quarter_lengths)

        # Adding the full measure duration to div_list as it's valid for all scenarios
        div_list.extend([full_measure_duration, full_measure_duration, full_measure_duration, full_measure_duration, full_measure_duration, full_measure_duration])

        return div_list

    def create_slash(chord_duration, altered_pitches):
        if user_clef == clef.TrebleClef():
            if "B-" in altered_pitches:
                slash_note = note.Note("B-4")
                slash_note.pitch.accidental.displayStatus = False
            else:
                slash_note = note.Note("B4")
        else:
            if "D-" in altered_pitches:
                slash_note = note.Note("D-4")
                slash_note.pitch.accidental.displayStatus = False
            else:
                slash_note = note.Note("D4")
        slash_note.notehead = "slash"
        slash_note.duration.quarterLength = chord_duration
        return slash_note

    def insert_chord(chord_progression, measure_number, offset, chord_object, duration, output_type = "written"):
        # Calculate remaining duration in the measure
        remaining_duration = chord_progression.timeSignature.barDuration.quarterLength - offset

        # Adjust the duration if it exceeds the remaining duration in the measure
        if duration > remaining_duration:
            duration = remaining_duration

        chord_object.duration.quarterLength = duration
        inserted_notes = None

        if len(chord_progression.measure(measure_number).getElementsByOffset(offset)) > 0:
            chord_progression.measure(measure_number).replace(offset, chord_object)
        else:
            chord_progression.measure(measure_number).insert(offset, chord_object)
            
        if output_type == "slashes":
            altered_pitches = [p.name for p in chord_progression.keySignature.alteredPitches]
            inserted_notes = create_slash(duration, altered_pitches)
            chord_progression.measure(measure_number).insert(offset, inserted_notes)
        elif output_type == "written":
            inserted_notes = chord.Chord(chord_object.pitches, duration = chord_object.duration)
            chord_progression.measure(measure_number).insert(offset, inserted_notes)
        elif output_type == "symbols":
            inserted_notes = note.Rest(chord_object.duration.quarterLength)
            chord_progression.measure(measure_number).insert(offset, inserted_notes)
        
        updated_offset = chord_progression.measure(measure_number).offset + offset + duration
        return updated_offset if updated_offset < chord_progression.timeSignature.barDuration.quarterLength else 0, chord_object, inserted_notes

    ### generate key signature, time signature, tonic and dominant chords ###
    key_sig = key.Key(random.choice(input_key_sig) if len(input_key_sig) > 0 else random.choice(["C", "G", "D", "A", "E", "B", "F#", "G-", "D-", "A-", "E-", "B-", "F"]))
    time_sig, meter_division_count, meter_division = generate_time_elements(input_time_sig[0], input_time_sig[1]) if (len(input_time_sig[0]) + len(input_time_sig[1])) > 1 else generate_time_elements()
    major_scale = scale.MajorScale(key_sig.asKey("major").tonic)
    tonic_chord = generate_chord([major_scale.getTonic().name], [""])
    dom_chord = generate_chord([major_scale.getDominant().name], [""])

    ### generate stream and number of measures###
    chord_progression = stream.Stream()
    number_of_measures = random.choice(score_length) if type(score_length) == list else score_length or random.randrange(1, 4)
    for m in range(1, number_of_measures + 1):
        chord_progression.append(stream.Measure(number = m))
    chord_progression.keySignature = key_sig
    chord_progression.timeSignature = time_sig

    # Distribute chords throughout measures
    tonic_or_dom = [tonic_chord, dom_chord]
    for c in range(number_of_measures, 0, -1):
        previous_chord = None
        previous_notation = None
        offset_count = 0
        divisions = calculate_divisions(meter_division, meter_division_count, min_division_level)
        random_division = random.choice(divisions)
        for div in random_division if isinstance(random_division, list) else [random_division]:
            selected_chord = chord.Chord(random.choice(tonic_or_dom).pitches)
            selected_chord.duration.quarterLength = div
            reharmed_chord = reharm_chord(selected_chord, major_scale, previous_chord, diatonic, max_num_extensions)
            if reharmed_chord is None:
                if previous_chord is not None:
                    previous_chord.duration.quarterLength += div ## alter previous chord duration
                if previous_notation is not None:
                    previous_notation.duration.quarterLength += div
                offset_count += div
                continue
            for single_chord in reharmed_chord if len(reharmed_chord) == 2 else [reharmed_chord]:
                offset_count, previous_chord, previous_notation = insert_chord(chord_progression, c, offset_count, single_chord, single_chord.duration.quarterLength, output_type)

    return chord_progression

def generate_interval(start_pitch = None, specific_interval = [], specific_duration = None, stand_alone = True):
    if len(specific_interval) != 0:
        new_interval = interval.Interval(random.choice(specific_interval))
    else:
        new_interval = interval.Interval(random.randrange(-15, 15, 1))
    
    if stand_alone == False:
        return new_interval

    else:
        start_note = note.Note()
        if start_pitch != None:
            start_note.pitch = start_pitch
        else:
            start_note.pitch.midi = random.randrange(57, 73, 1)

        new_interval.pitchStart = start_note.pitch
        end_note = note.Note(new_interval.pitchEnd)

        if specific_duration != None:
            start_note.duration.quarterLength = specific_duration
        else:
            duration_choices = [1, 2]
            start_note.duration.quarterLength = random.choice(duration_choices)
        end_note.duration.quarterLength = start_note.duration.quarterLength

        new_measure = stream.Measure(start_note)
        new_measure.append(end_note)
        new_stream = stream.Stream()
        new_stream.append(new_measure)

        return new_stream.makeNotation(), new_interval

def generate_scale(scale_tonic_list = [], mode_list = [], specified_duration=None):
    new_stream = stream.Stream()
    if len(scale_tonic_list) != 0: #scale_tonic should be in form of list
        tonic_list_choice = random.choice(scale_tonic_list)
        root_note = note.Note(tonic_list_choice)
    else:
        root_note = note.Note()
        root_note.pitch.midi = random.randrange(57, 73, 1)

    if specified_duration != None:
        duration_select = specified_duration
    else:
        duration_choices = [0.5, 1]
        duration_select = random.choice(duration_choices)

    if len(mode_list) != 0:
        mode_select = master_scale_dict[random.choice(mode_list)]
    else:
        mode_select = master_scale_dict[random.choice(scale_key_list)]

    scale_pitches = mode_select.getRealization(root_note.pitch, 1)
    new_scale_string_form = [str(scale_note) for scale_note in scale_pitches]
    if sum(s.count('-') for s in new_scale_string_form) >= len(scale_pitches) or sum(s.count('#')  for s in new_scale_string_form) >= len(scale_pitches):
        note_respell = True
    else:
        if scale_pitches[0].name == "F#" and random.choice([0, 1]) == 1:
            note_respell = True
        else:
            note_respell = False

    for n in scale_pitches:
        if note_respell == True:
            temp_note = note.Note(n.getEnharmonic())
        else:
            temp_note = note.Note(n)
        temp_note.duration.quarterLength = duration_select
        new_stream.append(temp_note)

    return new_stream.makeMeasures(), mode_select, scale_pitches

def generate_excerpt(input_key_sig = [], diatonic = True, score_length=None, include_chords=True, input_time_sig = [[], []], melody_subdivision = 4, chord_subdivision_level = 3):
    
    chord_progression = generate_chord_progression(input_key_sig, diatonic, score_length=score_length, output_type="symbols", input_time_sig=input_time_sig, min_division_level=chord_subdivision_level)

    excerpt = generate_full_melody(subdivision = melody_subdivision, input_chord_progression = chord_progression, diatonic=diatonic)
    excerpt = excerpt.makeNotation()

    return stream.Score(excerpt)

def generate_rhythm(denominator_list = [], numerator_list = [], number_of_measures=None, smallest_value=0.25):
    new_stream = stream.Stream()
    time_elements = generate_time_elements(denominator_list, numerator_list)
    time_sig = time_elements[0]
    new_stream.timeSignature = time_sig
    new_stream.staffLines = 1

    #create measures
    if number_of_measures != None:
        random_number_of_measures = number_of_measures
    else:
        random_number_of_measures = random.choice([1, 2, 3])
    for m in range(1, random_number_of_measures + 1):
        new_stream.append(stream.Measure(number = m))

    #create rhythms and rests
    beat_value = 1
    rhythm_list = []
    for m in range(random_number_of_measures):
        temp_measure_list = []
        temp_ql_list = []
        if time_sig.denominator == 4:
            for n in range(time_sig.numerator):
                beat_value = 1
                temp_measure_list.append(1)
                temp_ql_list.append(1)
        elif time_sig.denominator == 8:
            for n in range(int(time_sig.numerator / 3)):
                beat_value = 1.5
                temp_measure_list.append(1.5)
                temp_ql_list.append(1.5)

        edit_options = ["none", "split", "merge"]
        for r in range(3): #number of iterations
            random_index = random.randrange(0, len(temp_measure_list), 1) #choose random note in measure

            edit_choice = random.choice(edit_options)

            if edit_choice == "split" and float(temp_measure_list[random_index]) > smallest_value:
                if temp_measure_list[random_index] == 1.5: #we need to take into consideration meter
                    div = 3
                else:
                    div = 2
                split_value = round(float(temp_measure_list[random_index]) / div, 2)
                temp_measure_list[random_index] = split_value
                for d in range(div - 1):
                    temp_measure_list.insert(random_index + 1, split_value)

            elif edit_choice == "merge":
                if len(temp_measure_list) > 1:
                    if random_index == len(temp_measure_list) - 1:
                        merge_direction = -1
                    elif random_index == 0:
                        merge_direction = 1
                    else:
                        merge_direction = random.choice([-1, 1]) 
        
                    merge_note = float(temp_measure_list[random_index]) + float(temp_measure_list[random_index + merge_direction])
                    temp_measure_list[random_index] = merge_note
                    if random_index + merge_direction >= 0:
                        temp_measure_list.pop(random_index + merge_direction)

        rhythm_list.append(temp_measure_list)


    for measure_number, temp_measure in enumerate(rhythm_list):
        for ind, note_duration in enumerate(temp_measure):
            if random.choice(["note", "note", "rest"]) == "rest" and sum(temp_measure[:ind]) % beat_value == 0:
                new_note = note.Rest(note_duration)
            else:
                new_note = note.Note("E4")
                new_note.duration.quarterLength = note_duration
            new_stream.measure(measure_number + 1).append(new_note)
    
    new_stream.makeTies()
    new_stream.makeNotation()

    return new_stream

def generate_arpeggio(arp_root=None, arp_quality=None, arp_duration=None, arp_inversion=None):

    new_stream = stream.Stream()
    chord_object = generate_chord(chord_root_list=arp_root, chord_quality_list=arp_quality)
    if arp_inversion != None:
        chord_object.inversion = arp_inversion
    back_down_pitches = list(reversed(chord_object.pitches[:-1]))
    arp_pitches = list(chord_object.pitches) + back_down_pitches

    if arp_duration != None:
        random_duration = arp_duration
    else:
        duration_choices = [0.5, 1]
        random_duration = random.choice(duration_choices)

    for p in arp_pitches:
        new_note = note.Note(p)
        new_note.duration.quarterLength = random_duration
        new_stream.append(new_note)

    return new_stream.makeMeasures(), [p.nameWithOctave for p in new_stream.pitches], chord_object

def generate_note_value(specific_note_values=[], rest_or_note=None):
    new_stream = stream.Stream()
    new_stream.staffLines = 1
    if rest_or_note == None:
        rest_or_note = random.choice(["note", "rest"])
        
    if rest_or_note == "note":
        new_note = note.Note("E4")
    elif rest_or_note == "rest":
        new_note = note.Rest()

    if len(specific_note_values) != 0:
        new_note.duration.quarterLength = random.choice(specific_note_values)
    else:
        new_note.duration.quarterLength = random.choice([0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6])

    new_stream.append(new_note)

    return new_stream, new_note

### Secondary Functions ###

def generate_chord_scale(chord_object=None, key_sig_or_scale=None, previous_chord_scale_pitches=None, diatonic=False):
    common_notes_ratio_threshold = 0.05

    def select_best_scale_type(chord_object, chord_quality, key_sig_or_scale=None, previous_chord_scale_pitches=None):
        possible_scale_types = chord_scale_dict[chord_quality]
        best_scale_types_for_key_signature = []
        highest_key_sig_common_note_ratio = 0

        if key_sig_or_scale is not None:
            key_signature_pitches = add_enharmonic_equivalents(key_sig_or_scale.getScale().getPitches() if 'Scale' not in key_sig_or_scale.classSet else key_sig_or_scale.pitches)
            for scale_type in possible_scale_types:
                scale_realization = master_scale_dict[scale_type].getRealization(chord_object.root(), 1)
                scale_type_pitches = add_enharmonic_equivalents(scale_realization)
                common_notes_ratio = len(set(key_signature_pitches).intersection(scale_type_pitches)) / len(scale_realization)
                if abs(common_notes_ratio - highest_key_sig_common_note_ratio) < common_notes_ratio_threshold:
                    best_scale_types_for_key_signature.append(scale_type)
                elif common_notes_ratio > highest_key_sig_common_note_ratio:
                    highest_key_sig_common_note_ratio = common_notes_ratio
                    best_scale_types_for_key_signature = [scale_type]

        if previous_chord_scale_pitches is not None and len(best_scale_types_for_key_signature) > 1:
            previous_chord_pitches = add_enharmonic_equivalents(previous_chord_scale_pitches)
            best_scale_types_for_chord_progression = []
            highest_previous_chord_common_note_ratio = 0

            for scale_type in best_scale_types_for_key_signature:
                scale_realization = master_scale_dict[scale_type].getRealization(chord_object.root(), 1)
                scale_type_pitches = add_enharmonic_equivalents(scale_realization)
                common_notes_ratio = len(set(previous_chord_pitches).intersection(scale_type_pitches)) / len(scale_realization)
                if abs(common_notes_ratio - highest_previous_chord_common_note_ratio) < common_notes_ratio_threshold:
                    best_scale_types_for_key_signature.append(scale_type)
                elif common_notes_ratio > highest_previous_chord_common_note_ratio:
                    highest_previous_chord_common_note_ratio = common_notes_ratio
                    best_scale_types_for_key_signature = [scale_type]

            if best_scale_types_for_chord_progression:
                return random.choice(best_scale_types_for_chord_progression)

        return random.choice(best_scale_types_for_key_signature)

    if diatonic:
        if 'Scale' not in key_sig_or_scale.classSet:
            key_sig_or_scale = key_sig_or_scale.getScale()
        return key_sig_or_scale.tonic, key_sig_or_scale.name, key_sig_or_scale.getPitches()
    chord_scale_tonic = chord_object.root()
    chord_quality = get_chord_quality(chord_object)
    chord_scale_name = select_best_scale_type(chord_object, chord_quality=chord_quality, key_sig_or_scale=key_sig_or_scale, previous_chord_scale_pitches=previous_chord_scale_pitches)
    starting_scale_pitch = chord_object.root()
    starting_scale_pitch.octave = 4
    chord_scale_pitches = [m for m in master_scale_dict[chord_scale_name].getRealization(chord_object.root(), 1, minPitch=starting_scale_pitch)]
    return chord_scale_tonic, chord_scale_name, chord_scale_pitches

def generate_full_melody(subdivision=4, input_chord_progression=None, diatonic=False):    
    def compatible_pitches(chord_symbols, chord_scale_pitches, tone_type):
        if tone_type == "chord tone":
            chord_pitches_sets = [set(chord_symbol.pitchNames) for chord_symbol in chord_symbols]
            good_pitches = chord_scale_pitches.intersection(*chord_pitches_sets)  # Intersection of all sets
        else:
            remove_notes = set()
            if tone_type == "downbeat non-chord tone":
                for chord_symbol in chord_symbols:
                    if get_chord_quality(chord_symbol) not in ["7b9", "7b9#5", "+7b9"]:
                        remove_notes |= set()
                        for c in chord_symbol.pitchNames:
                            for i in chord_scale_pitches:
                                minor_second_check = interval.Interval(pitch.Pitch(c), pitch.Pitch(i)).semitones
                                if minor_second_check > 12:
                                    minor_second_check = minor_second_check - 12
                                if minor_second_check == 1:
                                    remove_notes.add(i)
            good_pitches = chord_scale_pitches - remove_notes  # Difference of sets
            for chord_symbol in chord_symbols:
                good_pitches -= set(chord_symbol.pitchNames)
            
        return list(good_pitches) if good_pitches else list(chord_scale_pitches)

    def note_settings(rhythmic_duration_list, rhythmic_duration, offset_list, offset_count, previous_note, previous_measure, last_measure=False):
        offset_list = offset_list[:-1]
        tone_type_choices = ["chord tone", "chord tone", "downbeat non-chord tone", "offbeat non-chord tone"]
        note_or_rest_choices = ["note", "note", "rest", "note", "note", "note"]

        if rhythmic_duration == sum(rhythmic_duration_list):
            tone_type = "chord tone"
            note_or_rest = "note"
            return tone_type, note_or_rest
        
        if last_measure and "rest" in note_or_rest_choices:
            note_or_rest_choices.remove("rest")

        if previous_measure is not None:
            rest_list = [p for p in previous_measure.getElementsByClass("Rest")]
            if len(rest_list) > 0:
                for r in rest_list:
                    if r.offset != 0 and "rest" in note_or_rest_choices:
                        note_or_rest_choices.remove("rest")
            elif "rest" in note_or_rest_choices:
                note_or_rest_choices.remove("rest")

        if offset_count == 0:
            tone_type_choices.remove("offbeat non-chord tone")
            tone_type = "chord tone" if rhythmic_duration > sum(offset_list) / len(offset_list) else random.choice(tone_type_choices)
            note_or_rest = random.choice(note_or_rest_choices)
        elif offset_count in offset_list:
            tone_type_choices.remove("offbeat non-chord tone")
            tone_type = "chord tone" if rhythmic_duration > sum(offset_list) / len(offset_list) else random.choice(tone_type_choices)
            note_or_rest = random.choice(note_or_rest_choices)
            if note_or_rest == "rest" and previous_note is not None and not previous_note.isRest:
                note_or_rest = "note"
        else:
            tone_type_choices.remove("downbeat non-chord tone")
            tone_type = random.choice(tone_type_choices)
            note_or_rest = "note"

        return tone_type, note_or_rest

    def note_pitch(compatible_pitches, chord_symbol, previous_note=None): ### really flesh this out
        pitch_choice = random.choice(compatible_pitches)

        if previous_note is not None and chord_symbol.third is not None and interval.Interval(chord_symbol.third, previous_note.pitch).simpleName == "m2":
            if previous_note.duration.quarterLength >= 1:
                pitch_choice = chord_symbol.third
            else:
                pitch_choice = random.choice([chord_symbol.third, chord_symbol.fifth])

        return pitch.Pitch(pitch_choice)

    def note_octave(current_pitch, melody_constraint=12, melody_limits=range(57, 83), previous_note=None, first_note=None):
        potential_octaves = [-2, -1, 0, 1, 2]

        if current_pitch.octave is None:
            current_pitch.octave = 4

        if first_note is not None:
            for octave in potential_octaves:
                if abs(first_note.pitch.midi - (current_pitch.midi + 12 * octave)) > melody_constraint:
                    potential_octaves.remove(octave)

        if previous_note is not None:
            for octave in potential_octaves:
                if abs(previous_note.pitch.midi - (current_pitch.midi + 12 * octave)) > melody_constraint:
                    potential_octaves.remove(octave)

        for octave in potential_octaves:
            if not melody_limits[0] <= current_pitch.midi + 12 * octave < melody_limits[1]:
                potential_octaves.remove(octave)

        if 1 in potential_octaves and -1 in potential_octaves:
            potential_octaves.extend([1, -1])
        
        potential_octaves.extend([0, 0, 0])

        return pitch.Pitch(current_pitch.nameWithOctave).transpose(random.choice(potential_octaves) * 12)

    if not input_chord_progression:
        raise Exception("No chord progression provided")

    key_sig = input_chord_progression.keySignature
    subdivision_durations, quarter_durations, offset_list = get_subdivision_durations(input_chord_progression.timeSignature, subdivision)

    first_note = None
    previous_measure = None
    for measure in input_chord_progression.getElementsByClass('Measure'):
        offset_count = 0
        previous_chord = None
        previous_chord_scale_pitches = None
        previous_note = None
        rhythmic_durations = get_rhythmic_durations(subdivision_durations[:])

        for i, rhythmic_duration in enumerate(rhythmic_durations):
            chord_symbol = None
            tone_type, note_or_rest = note_settings(rhythmic_durations, 
                                                    rhythmic_duration, 
                                                    offset_list, 
                                                    offset_count, 
                                                    previous_note, 
                                                    previous_measure, 
                                                    last_measure=True if measure.measureNumber == len(input_chord_progression.getElementsByClass('Measure')) else False)
            elements = measure.getElementsByOffset(offset_count,
                                                   offsetEnd=offset_count + rhythmic_duration,
                                                   includeEndBoundary=False,
                                                   mustBeginInSpan=False,
                                                   mustFinishInSpan=False,
                                                   classList=[harmony.ChordSymbol, chord.Chord])
            if elements:
                chord_symbol = elements[0]
                previous_chord = elements[-1]
                all_chord_scale_pitches = set()
                for e in elements:
                    chord_root, chord_scale_name, chord_scale_pitches = generate_chord_scale(e, key_sig, previous_chord_scale_pitches, diatonic)
                    all_chord_scale_pitches.update([p.name for p in chord_scale_pitches])

            elif previous_chord:
                chord_symbol = previous_chord
                chord_root, chord_scale_name, chord_scale_pitches = generate_chord_scale(chord_symbol, key_sig, previous_chord_scale_pitches, diatonic)
                all_chord_scale_pitches.update([p.name for p in chord_scale_pitches])

            if note_or_rest == "note" or (i == len(rhythmic_durations) - 1 and len(measure.getElementsByClass(note.Note)) == 0):
                if chord_symbol:
                    chosen_pitch = note_pitch(compatible_pitches(elements, all_chord_scale_pitches, tone_type), chord_symbol, previous_note=previous_note)
                    chosen_note = note.Note(note_octave(chosen_pitch, previous_note=previous_note, first_note=first_note), quarterLength=rhythmic_duration)
                    measure.insert(offset_count, chosen_note)
                    if i == 0 and measure.measureNumber == 1:
                        first_note = chosen_note
                    previous_note = chosen_note
                    previous_chord_scale_pitches = all_chord_scale_pitches
                else:
                    print(chord_symbol)
                    raise Exception("No chord symbol found for note")
            elif note_or_rest == "rest":
                measure.insert(offset_count, note.Rest(quarterLength=rhythmic_duration))
            offset_count += rhythmic_duration

        previous_measure = measure
        ### Clean up measure ###
        measure = measure.makeRests(fillGaps=True)
        measure = measure.makeBeams()

    input_chord_progression = input_chord_progression.makeNotation()

    return input_chord_progression

def reharm_chord(chord_object, major_scale, previous_chord=None, diatonic=True, max_num_extensions=None):
    def calculate_new_dom_divisions(chord_duration):
        div_list = []
        prime_numbers = [3, 5, 7, 11, 13, 17]

        if chord_duration in prime_numbers:
            bigger_split = math.ceil(int(chord_duration) / 2)
            smaller_split = chord_duration - bigger_split
            div_list.extend(random.choice([[bigger_split, smaller_split], [smaller_split, bigger_split]]))
        else:
            div_list.extend([chord_duration / 2, chord_duration / 2])
        
        return div_list

    def common_tone_check(chord_a, chord_b):
        chord_a_pitches = [p.name for p in chord_a.pitches]
        chord_b_pitches = [p.name for p in chord_b.pitches]
        #remove unecessary extensions
        if all(p in chord_a_pitches for p in chord_b_pitches) == True:
            return True
        else:
            return False

    # Define reharmonization methods
    reharm_methods = {
        "thirds": lambda: (None, move_in_thirds(chord_object, major_scale, random.randrange(-1, 2, 1), random.randrange(1, 3, 1), diatonic, max_num_extensions)),
        "add extensions": lambda: (None, add_extensions(chord_object, major_scale, diatonic, max_num_extensions)),
        "quality": lambda: (None, change_quality(chord_object, diatonic=diatonic, input_scale=major_scale, max_num_extensions=max_num_extensions)),
        "tritone": lambda: (None, tritone_sub(chord_object)) if chord_object.pitches == dom_chord.pitches else (None, chord_object),
        "retroactive dominant": lambda: retroactive_dom(chord_object, chord_object.duration.quarterLength, major_scale, diatonic) if chord_object.duration.quarterLength >= 2 else (None, chord_object)
    }

    if diatonic:
        reharm_methods.pop("quality")
        reharm_methods.pop("tritone")
        reharm_methods.pop("retroactive dominant")
    if chord_object.duration.quarterLength >= 2 and reharm_methods.get("retroactive dominant"):
        reharm_methods.pop("retroactive dominant")

    dom_chord = generate_chord([major_scale.getDominant().name], [""])

    iter_num = 2
    max_attempts = 5
    attempt = 0
    previous_reharm = None
    previous_new_dom = None
    while iter_num > 0:
        random_choice = random.choice(list(reharm_methods.keys()))
        new_dom, reharm = reharm_methods[random_choice]()
        previous_reharm = chord.Chord(reharm.pitches)
        previous_new_dom = chord.Chord(new_dom.pitches) if new_dom is not None else None
        attempt = 0
        while attempt < max_attempts:
            try:
                reharm = fix_chord_spelling(reharm)
                chord_symbol = harmony.chordSymbolFromChord(reharm)
                if new_dom:
                    new_dom = fix_chord_spelling(new_dom)
                    new_dom_chord_symbol = harmony.chordSymbolFromChord(new_dom)
                iter_num -= 1
            except pitch.AccidentalException:
                reharm = previous_reharm
                new_dom = previous_new_dom
            finally:
                attempt += 1
                if attempt >= max_attempts:
                    break

    # if two chords in a row have the same notes, combine them
    if previous_chord and common_tone_check(previous_chord, reharm):
        return None

    reharm.duration.quarterLength = chord_object.duration.quarterLength
    chord_symbol.duration.quarterLength = chord_object.duration.quarterLength

    if new_dom:
        divisions = calculate_new_dom_divisions(reharm.duration.quarterLength) # add chord symbols
        new_dom_chord_symbol.duration.quarterLength = divisions[0]
        chord_symbol.duration.quarterLength = divisions[1]
        return new_dom_chord_symbol, chord_symbol
    
    return chord_symbol
           
def reharm_progression(chord_progression, diatonic=True, output_type="written"):
    def calculate_new_dom_divisions(chord_duration):
        div_list = []
        prime_numbers = [3, 5, 7, 11, 13, 17]

        if chord_duration in prime_numbers:
            bigger_split = math.ceil(int(chord_duration) / 2)
            smaller_split = chord_duration - bigger_split
            div_list.extend(random.choice([[bigger_split, smaller_split], [smaller_split, bigger_split]]))
        else:
            div_list.extend([chord_duration / 2, chord_duration / 2])
        
        return div_list

    def create_slash():
        slash_note = note.Note("B4") if user_clef == clef.TrebleClef() else note.Note("D3")
        slash_note.notehead = "slash"
        slash_note.duration.quarterLength = reharm.duration.quarterLength
        return slash_note

    def common_tone_check(chord_a, chord_b):
        chord_a_pitches = [p.name for p in chord_a.pitches]
        chord_b_pitches = [p.name for p in chord_b.pitches]
        #remove unecessary extensions
        if all(p in chord_b_pitches for p in chord_a_pitches) == True:
            return True
        else:
            return False

    # Define reharmonization methods
    reharm_methods = {
        "thirds": lambda: (None, move_in_thirds(reharm, major_scale, random.randrange(-1, 2, 1), random.randrange(1, 3, 1))),
        "add extensions": lambda: (None, add_extensions(reharm, major_scale, diatonic)),
        "quality": lambda: (None, change_quality(reharm)) if diatonic else (None, reharm),
        "tritone": lambda: (None, tritone_sub(reharm)) if chord_object.pithces == dom_chord.pitches else (None, reharm),
        "retroactive dominant": lambda: retroactive_dom(reharm, chord_object.duration.quarterLength, major_scale, diatonic) if chord_object.duration.quarterLength >= 2 else (None, reharm)
    }

    major_scale = chord_progression.keySignature.getScale()
    dom_chord = generate_chord([major_scale.getDominant().name], [""])

    for measure in chord_progression:
        prev_chord = None
        if measure.measureNumber is not None:
            for object_number in range(len(measure)-1, -1, -1):  # iterate over measure in reverse
                chord_object = measure[object_number]
                reharm = chord_object.simplifyEnharmonics()

                iter_num = 2
                max_attempts = 5
                attempt = 0
                previous_reharm = None
                previous_new_dom = None
                while iter_num > 0:
                    random_choice = random.choice(list(reharm_methods.keys())) if diatonic else random.choice(list(reharm_methods.keys())[:2])
                    new_dom, reharm = reharm_methods[random_choice]()
                    previous_reharm = chord.Chord(reharm.pitches)
                    previous_new_dom = chord.Chord(new_dom.pitches) if new_dom is not None else None
                    attempt = 0
                    while attempt < max_attempts:
                        try:
                            reharm = fix_chord_spelling(reharm)
                            chord_symbol = harmony.chordSymbolFromChord(reharm)
                            if new_dom:
                                new_dom = fix_chord_spelling(new_dom)
                                new_dom_chord_symbol = harmony.chordSymbolFromChord(new_dom)
                            iter_num -= 1
                        except pitch.AccidentalException:
                            reharm = previous_reharm
                            new_dom = previous_new_dom
                        finally:
                            attempt += 1
                            if attempt >= max_attempts:
                                break
                
                # if two chords in a row have the same notes, combine them
                if prev_chord and common_tone_check(prev_chord, reharm) == True:
                    reharm.duration.quarterLength += prev_chord.duration.quarterLength
                    measure.remove(measure[object_number+1])

                reharm.duration.quarterLength = chord_object.duration.quarterLength

                if output_type != "written":  # add chord symbols
                    if new_dom:
                        divisions = calculate_new_dom_divisions(reharm.duration.quarterLength)
                        new_dom.duration.quarterLength = divisions[0]
                        chord_symbol.duration.quarterLength = divisions[1]
                        chord_progression.measure(measure.measureNumber).replace(chord_object, new_dom_chord_symbol)
                        chord_progression.measure(measure.measureNumber).insert(chord_object + reharm.duration.quarterLength, chord_symbol)
                        if output_type == "slashes":
                            chord_progression.measure(measure.measureNumber).replace(chord_object, create_slash())
                            chord_progression.measure(measure.measureNumber).insert(chord_object + reharm.duration.quarterLength, create_slash())                 
                    else:
                        chord_progression.measure(measure.measureNumber).replace(chord_object, chord_symbol)
                        if output_type == "slashes":
                            chord_progression.measure(measure.measureNumber).replace(chord_object, create_slash())

                else:
                    if new_dom:
                        divisions = calculate_new_dom_divisions(reharm.duration.quarterLength)
                        new_dom.duration.quarterLength = divisions[0]
                        reharm.duration.quarterLength = divisions[1]
                        chord_progression.measure(measure.measureNumber).replace(chord_object, new_dom)
                        chord_progression.measure(measure.measureNumber).insert(chord_object + reharm.duration.quarterLength, reharm)
                    else:
                        chord_progression.measure(measure.measureNumber).replace(chord_object, reharm)

                prev_chord = reharm

    return chord_progression

def move_in_thirds(input_chord, input_scale, direction, iterate=2, diatonic=True, max_num_extensions=None):
    if direction == 0 or get_chord_quality(input_chord) not in chord_interval_list:
        return input_chord

    semitone_list = [interval.Interval(n) for n in chord_by_interval_dict[get_chord_quality(input_chord)]]
    thirds_as_string = semitone_list[0].simpleName
    for i in range(len(semitone_list) - 1):
        thirds_as_string += interval.subtract([semitone_list[i + 1], semitone_list[i]]).simpleName
        
    if not all(i == '3' for i in thirds_as_string if i.isdigit()):
        return input_chord

    thirds_pattern_dict = {
        "major/minor": 'm3M3m3M3m3M3m3',
        "dim/dom": 'M3m3m3M3',
        "dim": 'm3m3m3m3',
        "aug": 'M3M3M3M3',
        "lydian dominant": 'M3m3m3M3M3m3'
    }

    if diatonic:
        thirds_pattern_dict.pop("dim")
        thirds_pattern_dict.pop("aug")
        thirds_pattern_dict.pop("lydian dominant")

    if next((pattern for pattern in thirds_pattern_dict if thirds_as_string in thirds_pattern_dict[pattern]), None) == None:
        return input_chord

    re_pattern = re.compile('M3|m3')
    thirds_list = re_pattern.findall(thirds_as_string)
    keep_extensions = random.choice([True, False]) if max_num_extensions is None else True
    index_from_direction = 0 if direction == -1 else -1
    scale_pitches = [p.name for p in input_scale.pitches]
    new_chord = chord.Chord(input_chord.pitches)

    for i in range(iterate):
        new_interval = (3 if thirds_list[index_from_direction] == 'M3' else 4) * direction
        new_pitch = interval.transposePitch(new_chord[index_from_direction].pitch, new_interval)
        for p in new_chord.pitches:
            if interval.Interval(p, new_pitch).simpleName == 'm2':
                break
        if diatonic and new_pitch.name not in scale_pitches:
            break
        new_chord.add(new_pitch)
        thirds_list.append(interval.Interval(new_interval).simpleName) if direction == 1 else thirds_list.insert(0, interval.Interval(new_interval).simpleName)

    if not keep_extensions:
        new_chord = chord.Chord(new_chord.pitches[:3])
    if max_num_extensions is not None:
        new_chord = chord.Chord(new_chord.pitches[:3 + max_num_extensions])

    return new_chord

def change_quality(input_chord, input_quality=None, diatonic=True, input_scale=None, max_num_extensions=None):
    chord_intervals = [int(ly.text) for ly in reversed(input_chord.annotateIntervals(inPlace=False).lyrics)]

    if input_quality is not None:
        return generate_chord([input_chord.root()], [input_quality])
    
    if max_num_extensions is not None:
        chord_intervals = chord_intervals[:3 + max_num_extensions]

    quality_ranges = {
        frozenset([9, 11, 13]): range(37, 58),
        frozenset([7]): range(9, 37),
        frozenset(): list(filter(lambda x: x != 3, range(0, 9)))
    }

    quality_choices_list = None
    for interval_set, quality_range in quality_ranges.items():
        if set(chord_intervals) & interval_set:
            quality_choices_list = list(quality_range)
            break
        else:
            quality_choices_list = list(quality_ranges[frozenset()])

    input_scale_pitches = [p.name for p in input_scale.pitches]
    for choice in quality_choices_list:
        if max_num_extensions is not None and len(chord_by_interval_dict[chord_interval_list[choice]]) != len(chord_intervals):
            quality_choices_list.remove(choice)
        if chord_by_interval_dict[chord_interval_list[choice]] == chord_intervals:
            quality_choices_list.remove(choice)  # remove original quality from choices
        if diatonic and all(p in input_scale_pitches for p in generate_chord([input_chord.root()], chord_interval_list[choice]).pitchNames):
            quality_choices_list.remove(choice)
    
    new_chord = generate_chord([input_chord.root()], chord_interval_list[quality_choices_list[0]:quality_choices_list[-1]])

    return new_chord

def add_extensions(input_chord, input_scale, diatonic=True, max_num_extensions=None):
    def extension_check(new_chord, max_num_extensions):
        if len(new_chord) >= 7:
            return False
        elif max_num_extensions is not None and len(new_chord) >= (3 + max_num_extensions):
            return False
        else:
            return True
        
    new_chord = chord.Chord(input_chord.pitches)
    iterate_number = random.choice([1, 1, 1, 1, 2, 2, 2, 3, 4])

    quality_to_scale = {
        "major": scale.LydianScale,
        "minor": scale.DorianScale,
        "augmented": scale.WholeToneScale,
        "diminished": dorian_flat5_scale._net.realizePitch if input_chord.isTriad or input_chord.isHalfDiminishedSeventh else whole_half_diminished_scale._net.realizePitch,
        "default": scale.DiatonicScale
    }

    ref_scale = quality_to_scale.get(input_chord.quality, quality_to_scale["default"])(input_chord[0]) if not diatonic else input_scale

    if extension_check(new_chord, max_num_extensions):
        for _ in range(iterate_number + 1):
            new_extension = ref_scale.nextPitch(new_chord[-1].nameWithOctave, scale.Direction.ASCENDING, stepSize=2)
            if interval.Interval(new_chord[1], new_extension).simpleName == "m2":
                new_extension = ref_scale.nextPitch(new_chord[-1].nameWithOctave, scale.Direction.ASCENDING, stepSize=4)
            if new_extension.simplifyEnharmonic().name not in new_chord.pitchNames:
                new_chord.add(new_extension.simplifyEnharmonic())
            if not extension_check(new_chord, max_num_extensions):
                break

    return fix_chord_spelling(new_chord)

def tritone_sub(input_chord):
    trione_chord = input_chord.transpose("d5")
    return trione_chord.simplifyEnharmonics()

def retroactive_dom(input_chord, chord_duration, input_scale, diatonic = True): #add condition for diatonicism
    ref_scale = scale.DiatonicScale(chord.Chord(input_chord.pitches).root())
    dom_chord = generate_chord([ref_scale.getDominant().nameWithOctave], [""])
    new_chord = chord.Chord(input_chord.pitches)
    new_chord.duration.quarterLength = chord_duration / 2
    dom_chord.duration.quarterLength = chord_duration / 2
    return dom_chord.simplifyEnharmonics(), new_chord.simplifyEnharmonics()

def generate_time_elements(numerators=[], denominators=[]):
    # Helper function to choose a random value from user-supplied or default choices
    def choose_value(default_choices, user_choices):
        return random.choice(user_choices if user_choices else default_choices)

    # Define default choices for numerators and denominators
    default_denominators = [4, 8]
    default_numerators = {
        4: [2, 3, 4, 5, 6, 7],
        8: [5, 6, 7, 9, 10, 12]
    }

    # Select denominator and corresponding numerator
    denominator = choose_value(default_denominators, denominators)
    numerator = choose_value(default_numerators[denominator], numerators)

    # Create time signature
    time_sig_string = f"{numerator}/{denominator}"
    time_sig = meter.TimeSignature(time_sig_string)

#create meter sequence
    prime_numbers = [3, 5, 7, 11, 13]
    meter_sequence = meter.MeterSequence(time_sig_string)
    if meter_sequence.numerator in prime_numbers and meter_sequence.numerator > 4:
        meter_seq_options = meter_sequence.getPartitionOptions()[:math.floor(meter_sequence.numerator / 2)]
        meter_division = list(random.choice(meter_seq_options))
    else:
        meter_division = list(meter_sequence.getPartitionOptions()[0])
    meter_division_count = len(meter_division)

    # Update time signature
    meter_sequence.load("+".join(meter_division))
    time_sig.beamSequence = meter_sequence
    time_sig.beatSequence = meter_sequence

    return time_sig, meter_division_count, meter_division

### Auxillary Functions ###

def get_chord_quality(chord_object):
    chord_symbol_figure = harmony.chordSymbolFromChord(chord_object).figure
    if chord_symbol_figure == 'Chord Symbol Cannot Be Identified': #brute force method
        interval_numbers = [ly.text for ly in reversed(chord_object.annotateIntervals(inPlace=False, stripSpecifiers=True).lyrics)]
        chord_intervals = [ly.text for ly in reversed(chord_object.annotateIntervals(inPlace=False, stripSpecifiers=False).lyrics)]
        rewritten_chord_intervals = [chord_intervals[0]]
        octave_flag = 0
        for index in range(1, len(chord_intervals)):
            if int(interval_numbers[index - 1]) > int(interval_numbers[index]) or octave_flag == 1:
                interval_quality = chord_intervals[index].replace(interval_numbers[index], "")
                fixed_interval = interval_quality + str(int(interval_numbers[index]) + 7)
                rewritten_chord_intervals.append(fixed_interval)
                octave_flag = 1
            else:
                rewritten_chord_intervals.append(chord_intervals[index])
        try:
            return list(chord_by_interval_dict.keys())[list(chord_by_interval_dict.values()).index(rewritten_chord_intervals)]
        except ValueError:
            return get_chord_quality(fix_chord_spelling(chord_object))
    else:
        chord_symbol_figure = chord_symbol_figure.replace(chord_object.root().name, "")
        return chord_symbol_figure

def add_enharmonic_equivalents(pitch_list):
    pitch_names_with_enharmonics = []
    for single_pitch in pitch_list:
        single_pitch = pitch.Pitch(single_pitch)
        pitch_names_with_enharmonics.append(single_pitch.name)
        pitch_names_with_enharmonics.extend(e.name for e in single_pitch.getAllCommonEnharmonics(alterLimit=2))
    return pitch_names_with_enharmonics

def get_rhythmic_durations(subdivision_list):
    iterations = random.randrange(0, len(subdivision_list) - 1)
    for _ in range(iterations):
        random_index = random.randrange(0, len(subdivision_list))
        if len(subdivision_list) == 1:
            break
        elif random_index != 0 and random_index != len(subdivision_list) - 1:
            left_or_right_index = subdivision_list[random_index + random.choice([-1, 1])]
            subdivision_list[random_index] = left_or_right_index + subdivision_list[random_index]
            subdivision_list.pop(subdivision_list.index(left_or_right_index))
        elif random_index == 0:
            subdivision_list[random_index] = subdivision_list[random_index + 1] + subdivision_list[random_index]
            subdivision_list.pop(random_index + 1)
        elif random_index == len(subdivision_list) - 1:
            subdivision_list[random_index] = subdivision_list[random_index - 1] + subdivision_list[random_index]
            subdivision_list.pop(random_index - 1)
    return subdivision_list

def get_subdivision_durations(time_signature, subdivision=4):
    duration_filter = {4: [1.5, 1.0], 8: [0.5, 0.5], 16: [0.25, 0.25]}

    offset_list = time_signature.getBeatOffsets()
    offset_list.append(time_signature.barDuration.quarterLength)
    beat_durations = []
    quarter_durations = []

    for i in range(len(offset_list) - 1):
        beat_duration = offset_list[i + 1] - offset_list[i]
        if beat_duration > duration_filter[subdivision][0]:
            subbeats = [duration_filter[subdivision][1]]*int(beat_duration / duration_filter[subdivision][1])
            beat_durations.extend(subbeats)
        else:
            beat_durations.append(beat_duration)

        # Record quarter durations
        if beat_duration > duration_filter[4][0]:
            quarter_subbeats = [duration_filter[4][1]]*int(beat_duration / duration_filter[4][1])
            quarter_durations.extend(quarter_subbeats)
        else:
            quarter_durations.append(beat_duration)

    return beat_durations, quarter_durations, offset_list

def fix_chord_spelling(chord_object):
    def respell_check(chord_object):
        pitch_strings = ''.join(chord_object.pitchNames)
        if any([p.accidental.modifier in ["##", "###", "####", "--", "---", "----"] for p in chord_object.pitches if p.accidental is not None]):
            return True
        elif chord_object.root().name in ["F-", "C-", "E#", "B#"]:
            return True
        else:
            return False

    if chord_object.root().name != chord_object.bass().name:
        chord_object.add(chord_object.root().name + "1")
    pitch_strings = ''.join(chord_object.pitchNames)
    if any(pitch_strings.count(p) > 1 for p in pitch_strings if p.isalpha()):
        chord_object = chord_object.simplifyEnharmonics()
    if respell_check(chord_object):
        fixed_chord = chord.Chord()
        for p in chord_object.pitches:
            possible_enharmonics = p.getAllCommonEnharmonics(alterLimit=1)
            if len(possible_enharmonics) > 0:
                fixed_chord.add(p.getAllCommonEnharmonics(alterLimit=1)[0])
            else:
                fixed_chord.add(p)
        fixed_chord = fixed_chord.closedPosition(forceOctave=4)
        return fixed_chord.simplifyEnharmonics()
    else:
        chord_object = chord_object.closedPosition(forceOctave=4)
        return chord_object

def convert_to_roman_numerals(chord_item, input_key):
    fixed_chord = fix_chord_spelling(chord_item)
    chord_symbol = harmony.chordSymbolFromChord(fixed_chord).figure
    extensions = chord_symbol.replace(fixed_chord.root().name, "")
    roman_numeral = roman.romanNumeralFromChord(fixed_chord, input_key)
    base_roman = roman_numeral.romanNumeral
    if base_roman.islower() == True and extensions[0] == "m":
        extensions = extensions[1:]
    # print(chord_symbol, base_roman)
    completed_roman_numeral = base_roman + extensions
    # print(completed_roman_numeral)
    return completed_roman_numeral

def generate_prompt_text(question_type, answer_type, language="en"):
    if language == "en":
        if question_type == "audio":
            prompt_text1 = "Listen"
        else:
            prompt_text1 = "Read"

        if answer_type in ["piano", "record"]:
            prompt_text2 = "play"
        elif "mc" in answer_type:
            prompt_text2 = "select"
        else:
            prompt_text2 = "type"

    elif language == "es":
        if question_type == "audio":
            prompt_text1 = "Escuche"
        else:
            prompt_text1 = "Lea"

        if answer_type in ["piano", "record"]:
            prompt_text2 = "toque"
        elif "mc" in answer_type:
            prompt_text2 = "seleccione"
        else:
            prompt_text2 = "escriba"

    prompt_text_full = prompt_text1 + " and " + prompt_text2
    return prompt_text_full

def m21_to_base64(m21_stream):
    # Create an exporter object from the musicXML module
    musicXML_exporter = musicxml.m21ToXml.GeneralObjectExporter(m21_stream)
    # Convert the music21 stream to a musicXML string
    # Convert the music21 stream to a musicXML string
    converted_stream_string = musicXML_exporter.parse()
    
    # Check if the converted stream is already bytes
    if isinstance(converted_stream_string, bytes):
        encoded_stream = base64.b64encode(converted_stream_string)
    else:
        encoded_stream = base64.b64encode(converted_stream_string.encode('utf-8'))
    
    # Return the encoded stream as a string
    return encoded_stream.decode('utf-8')

def m21_to_wav(m21_stream):
    base_path = os.path.dirname(os.path.abspath(__file__))
    soundfont_dir = os.path.join(base_path, "soundfonts")
    soundfont_path = os.path.join(soundfont_dir, random.choice(os.listdir(soundfont_dir)))

    midi_files_path = os.path.join(base_path, "midi_files")
    wav_files_path = os.path.join(base_path, "wav_files")

    with tempfile.NamedTemporaryFile(suffix=".mid", dir=midi_files_path, delete=False) as tf_midi:
        # Write the Music21 stream to a temporary MIDI file
        m21_stream.write("midi", fp=tf_midi.name)
        converted_midi = tf_midi.name

    # Use the same base name for the WAV file
    base_name = os.path.splitext(os.path.basename(converted_midi))[0]
    wav_file_path = os.path.join(wav_files_path, f"{base_name}.wav")

    # Convert the MIDI file to a WAV file using FluidSynth
    fs = FluidSynth(soundfont_path)
    fs.midi_to_audio(converted_midi, wav_file_path)

    # Clean up the temporary MIDI file if needed
    # os.remove(converted_midi)

    return wav_file_path

### Question Functions ###

def replace_pitch_placeholder(question_text, xml_render):
    pitch_string = xml_render.flatten().notes.stream()[0].name
    if "-" in pitch_string:
        pitch_string = pitch_string.replace("-", "b")
    return question_text.replace("*pitch*", pitch_string), None

def replace_note_value_placeholder(question_text, xml_render):
    if type(xml_render) == tuple:
        note_value_string = xml_render[1].duration.type + " note"
    else:
        note_value_string = xml_render.flatten().notes.stream()[0].duration.type + " note"
    return question_text.replace("*note value*", note_value_string), None

def replace_scale_mode_placeholder(question_text, xml_render):
    return question_text.replace("*scale mode*", xml_render[1].mode + " mode"), None

def replace_chord_quality_placeholder(question_text, xml_render):
    if type(xml_render) == tuple:
        chord_quality_string = harmony.chordSymbolFigureFromChord(xml_render[2], includeChordType=True)[1] + " chord"
    else:
        chord_quality_string = harmony.chordSymbolFigureFromChord(chord.Chord(xml_render.pitches), includeChordType=True)[1] + " chord"
    return question_text.replace("*chord quality*", chord_quality_string), None

def replace_scale_placeholder(question_text, xml_render):
    if xml_render[1].name in ["Whole Tone", "Half Whole Diminished", "Whole Half Diminished"] or xml_render[1].mode == None:
        scale_string = xml_render[2][0].name + " " + xml_render[1].type + " scale"
    else:
        scale_string = xml_render[2][0].name + " " + xml_render[1].mode + " scale"
    return question_text.replace("*scale*", scale_string), None

def replace_key_placeholder(question_text, xml_render):
    major_keys = ["C", "D-", "D", "E-", "E", "F", "F#", "G-", "G", "A-", "A", "B-", "B"]
    minor_keys = [x.lower() for x in major_keys]
    all_keys = major_keys + minor_keys
    key_select = key.Key(random.choice(all_keys)).name
    return question_text.replace("*key*", key_select), key_select

def replace_key_text_placeholder(question_text, xml_render):
    key_string = str(xml_render.keySignature.asKey())
    return question_text.replace("*key text*", key_string), None

def replace_beat_placeholder(question_text, xml_render):
    random_note = random.choice(xml_render.flatten().notesAndRests)
    random_note_measure = random_note.measureNumber
    random_note_beat = random_note.beat
    beat_string = "measure " + str(random_note_measure) + ", beat " + str(random_note_beat)
    return question_text.replace("*beat*", beat_string), random_note

def replace_chord_placeholder(question_text, xml_render):
    if type(xml_render) == tuple:
        chord_symbol = harmony.chordSymbolFromChord(xml_render[2]).figure
        chord_string = xml_render[2].root().name + harmony.chordSymbolFigureFromChord(xml_render[2], includeChordType=True)[1]
    else:
        chord_symbol = harmony.chordSymbolFromChord(xml_render.flatten().notes.stream()[0]).figure
        chord_string = chord.Chord(xml_render.flatten().notes.stream()[0]).root().name + harmony.chordSymbolFigureFromChord(xml_render.flatten().notes.stream()[0], includeChordType=True)[1]
    return question_text.replace("*chord*", random.choice([chord_symbol, chord_string])), chord_string

def replace_chord_tone_placeholder(question_text, xml_render):
    if type(xml_render) == tuple:
        chord_intervals = xml_render[2].annotateIntervals(inPlace=False)
    else:
        chord_intervals = xml_render.measure(1)[0].annotateIntervals(inPlace=False)
    chord_intervals = [ly.text for ly in reversed(chord_intervals.lyrics)]
    chord_tone_dict = {"1": "root", "2": "second", "3": "third", "4": "fourth", "5": "fifth", "6": "sixth", "7": "seventh", "9": "ninth", "11": "eleventh", "13": "thirteenth"}
    chord_tone_keys = [tone for tone in chord_tone_dict.keys() if tone in chord_intervals]
    random_chord_tone = random.choice(chord_tone_keys)
    return question_text.replace("*chord tone*", chord_tone_dict[random_chord_tone]), int(random_chord_tone)

def replace_directed_interval_placeholder(question_text, xml_render):
    random_int = random.randrange(-12, 12, 1)
    set_interval = interval.Interval(random_int)
    if random_int > 0:
        direction_string = "up a "
    elif random_int < 0:
        direction_string = "down a "
    else:
        direction_string = "by a "
    interval_string = direction_string + set_interval.niceName.lower()
    return question_text.replace("*directed interval*", interval_string), set_interval

def replace_inversion_placeholder(question_text, xml_render):
    inversion_integer = xml_render.measure(1)[0].inversion()
    inversion_list = list(range(0, 7))
    inversion_list.remove(inversion_integer)
    possible_inversions = inversion_list[:len(xml_render.measure(1)[0].pitches) - 1]
    set_inversion_int = random.choice(possible_inversions)
    inverted_chord = chord.Chord(xml_render.measure(1)[0].pitches)
    inverted_chord.inversion(set_inversion_int)
    set_inversion_string = inverted_chord.inversionText()
    return question_text.replace("*inversion*", set_inversion_string.lower()), set_inversion_int

def replace_measure_placeholder(question_text, xml_render):
    number_of_measures = xml_render.measure(-1).measureNumber
    random_measure = random.randrange(1, number_of_measures + 1)
    measure_string = "measure " + str(random_measure)
    return question_text.replace("*measure*", measure_string), random_measure

def replace_roman_numeral_placeholder(question_text, xml_render):
    random_scale_degree = random.randrange(1, len(xml_render.keySignature.asKey().getScale("major").pitches))
    roman_numeral = xml_render.keySignature.asKey().romanNumeral(random_scale_degree).figure
    return question_text.replace("*roman numeral*", roman_numeral), random_scale_degree

def replace_scale_degree_placeholder(question_text, xml_render):
    question_scale = scale.ConcreteScale(pitches=xml_render[0].pitches)
    random_scale_note = random.choice(xml_render[0].pitches)
    set_scale_degree = question_scale.getScaleDegreeFromPitch(random_scale_note)
    scale_degree_dict = {"1": "tonic", "2": "second", "3": "third", "4": "fourth", "5": "fifth", "6": "sixth", "7": "seventh", "8": "octave"}
    scale_degree_name_dict = {"1": "tonic", "2": "supertonic", "3": "mediant", "4": "subdominant", "5": "dominant", "6": "submediant", "7": "leading tone", "8": "tonic"}     
    return question_text.replace("*scale degree*", scale_degree_dict[str(set_scale_degree)]), set_scale_degree

def replace_simple_interval_placeholder(question_text, xml_render):
    random_int = random.randrange(-12, 12, 1)
    set_interval = interval.Interval(random_int)
    interval_string = set_interval.niceName.lower()
    return question_text.replace("*simple interval*", interval_string), set_interval

def replace_subdivision_placeholder(question_text, xml_render):
    original_duration = xml_render[1].duration.quarterLength #will have to tweak this
    subdivision_dict = {0.125: "32nd note", 0.25: "16th note", 0.5: "8th note", 0.75: "dotted 8th note", 1: "quarter note", 1.5: "dotted quarter note", 2: "half note", 4: "whole note"}
    subdiv_dict_keys = list(subdivision_dict.keys())
    choice_list = [s for s in subdiv_dict_keys if original_duration % s == 0 and s != original_duration]
    subdivision_choice = random.choice(choice_list)
    correct_answer = str(int(original_duration / subdivision_choice))
    return question_text.replace("*subdivision*", subdivision_dict[subdivision_choice]), correct_answer

placeholder_processors = {
    "*pitch*": replace_pitch_placeholder,
    "*note value*": replace_note_value_placeholder,
    "*scale mode*": replace_scale_mode_placeholder,
    "*chord quality*": replace_chord_quality_placeholder,
    "*scale*": replace_scale_placeholder,
    "*key*": replace_key_placeholder,
    "*key text*" : replace_key_text_placeholder,
    "*beat*": replace_beat_placeholder,
    "*chord*": replace_chord_placeholder,
    "*chord tone*": replace_chord_tone_placeholder,
    "*directed interval*": replace_directed_interval_placeholder,
    "*inversion*": replace_inversion_placeholder,
    "*measure*": replace_measure_placeholder,
    "*roman numeral*": replace_roman_numeral_placeholder,
    "*scale degree*": replace_scale_degree_placeholder,
    "*simple interval*": replace_simple_interval_placeholder,
    "*subdivision*": replace_subdivision_placeholder
}


### Answer Functions ###

def answer_chord_intervals(q_dict, mc=False):
    chord_intervals = q_dict[2].measure(1)[0].annotateIntervals(inPlace=False, stripSpecifiers=False)
    return [ly.text for ly in reversed(chord_intervals.lyrics)]

def answer_play_pitch(q_dict, mc=False):
    note_string_form = q_dict[2].flatten().notes.stream()[0].name
    if "-" in note_string_form:
        note_string_form = note_string_form.replace("-", "b")
    return note_string_form

def answer_convert_roman(q_dict, user_level, mc=False):
    answer_list = []
    correct_answer = harmony.chordSymbolFromChord(chord.Chord(roman.RomanNumeral(q_dict[3], q_dict[2].keySignature.asKey()).pitches)).figure
    if mc == False:
        return correct_answer
    elif mc == True:
        answer_list.append(correct_answer)
        while len(answer_list) != 4:
            random_quality = random.choice(["", "m", "+", "dim"])
            wrong_answer = harmony.chordSymbolFromChord(call_question_function("chord", user_level, {"1": [random_quality]})).figure
            if wrong_answer not in answer_list:
                answer_list.append(wrong_answer)
        random.shuffle(answer_list)
        return answer_list, answer_list.index(correct_answer) + 1

def answer_relative_minor_scale(q_dict, user_level, output="string", mc=False):
    answer_list = []
    current_scale_pitches = scale.DiatonicScale(q_dict[2][2][0])
    relative_minor_scale = current_scale_pitches.getRelativeMinor()
    correct_answer = [str(p.name) for p in relative_minor_scale.pitches]

    def create_scale_stream(scale_pitches, duration):
        scale_stream = stream.Stream()
        for pitch_name in scale_pitches:
            scale_note = note.Note(pitch_name)
            scale_note.duration.quarterLength = duration
            scale_stream.append(scale_note)
        scale_stream.makeMeasures()
        return scale_stream

    if output == "xml":
        correct_duration = q_dict[2][0].measure(1)[0].duration.quarterLength
        correct_answer = create_scale_stream(correct_answer, correct_duration)
        correct_answer = m21_to_base64(correct_answer)

    if not mc:
        return correct_answer

    answer_list.append(correct_answer)
    parallel_minor_scale = current_scale_pitches.getParallelMinor()
    parallel_minor = [str(p.name) for p in parallel_minor_scale.pitches]

    if output == "xml":
        parallel_minor = create_scale_stream(parallel_minor, correct_duration)

    answer_list.append(parallel_minor)

    mode_dict = {1: "ionian", 2: "dorian", 3: "phrygian", 4: "lydian", 5: "mixolydian", 7: "locrian"}
    scale_degrees = list(mode_dict.keys())

    while len(answer_list) != 4:
        random_scale_degree = random.choice(scale_degrees)
        wrong_pitch = current_scale_pitches.pitchFromDegree(random_scale_degree)
        mode_name = mode_dict[random_scale_degree]

        if output == "xml":
            wrong_answer = call_question_function("scale", user_level, {"0": [wrong_pitch], "1": [mode_name], "2": correct_duration})[0]
            if wrong_answer.pitches != correct_answer.pitches:
                wrong_answer = m21_to_base64(wrong_answer)
                answer_list.append(wrong_answer)
        else:
            wrong_answer = [str(p.name) for p in scale.AbstractDiatonicScale(mode_name).getRealization(wrong_pitch, 1)]
            if wrong_answer not in answer_list:
                answer_list.append(wrong_answer)

    random.shuffle(answer_list)
    correct_answer_index = answer_list.index(correct_answer) + 1

    return answer_list, correct_answer_index

def answer_diatonic_chord(q_dict, user_level, output="string", mc=False):
    answer_list = []
    current_scale = q_dict[2][2]
    random_scale_degree = random.randrange(1, len(current_scale), 1)
    triad_degrees = [random_scale_degree]

    for _ in range(2):
        random_scale_degree += 2
        next_degree = random_scale_degree if random_scale_degree <= 7 else random_scale_degree - 7
        triad_degrees.append(next_degree)

    diatonic_chord = chord.Chord([current_scale[triad_degrees[i]].name for i in range(3)])

    if output == "string":
        correct_answer = harmony.chordSymbolFromChord(diatonic_chord).figure
    else:  # output == "xml"
        correct_stream = stream.Stream()
        correct_stream.append(diatonic_chord)
        correct_answer = correct_stream
        correct_answer = m21_to_base64(correct_answer)

    if not mc:
        return correct_answer

    answer_list.append(correct_answer)

    while len(answer_list) != 4:
        random_scale_degree = random.randrange(1, len(current_scale), 1)
        random_quality = random.choice(["", "m", "+", "dim"])
        wrong_chord = call_question_function("chord", user_level, {"0": [current_scale[random_scale_degree]], "1": [random_quality], "2": False})
        wrong_chord_pitch_names = set(wrong_chord.pitchNames)

        if len(wrong_chord_pitch_names.intersection(set([p.name for p in current_scale]))) != len(wrong_chord.pitchNames):
            if output == "string":
                wrong_answer = harmony.chordSymbolFromChord(wrong_chord).figure
            else:  # output == "xml"
                wrong_stream = stream.Stream()
                wrong_stream.append(wrong_chord)
                wrong_answer = wrong_stream
                wrong_answer = m21_to_base64(wrong_answer)

            if wrong_answer not in answer_list:
                answer_list.append(wrong_answer)

    random.shuffle(answer_list)
    correct_answer_index = answer_list.index(correct_answer) + 1

    return answer_list, correct_answer_index

def answer_non_diatonic_chord(q_dict, user_level, output="string", mc=False):
    answer_list = []
    current_scale = q_dict[2][2]
    random_scale_degree = random.randrange(1, len(current_scale), 1)

    # Finding a non-diatonic chord
    while True:
        random_quality = random.choice(["", "m", "+", "dim"])
        wrong_chord = call_question_function("chord", user_level, {"0": [current_scale[random_scale_degree]], "1": [random_quality], "2": False})
        if len(set(wrong_chord.pitchNames).intersection(set([p.name for p in current_scale]))) != len(wrong_chord.pitchNames):
            break

    if output == "string":
        correct_answer = harmony.chordSymbolFromChord(wrong_chord).figure
    else:  # output == "xml"
        correct_stream = stream.Stream()
        correct_stream.append(wrong_chord)
        correct_stream.makeNotation()
        correct_answer = correct_stream
        correct_answer = m21_to_base64(correct_answer)

    if mc == False:
        return correct_answer
    else:
        answer_list.append(correct_answer)

        while len(answer_list) != 4:
            random_scale_degree = random.randrange(1, len(current_scale), 1)
            triad_degrees = [random_scale_degree]

        for n in range(2):
            degree_count = (triad_degrees[-1] + 2) % 7
            if degree_count == 0:
                degree_count = 7
            triad_degrees.append(degree_count)

        diatonic_chord = chord.Chord([current_scale[triad_degrees[0]].name, current_scale[triad_degrees[1]].name, current_scale[triad_degrees[2]].name])

        if output == "string":
            diatonic_chord_figure = harmony.chordSymbolFromChord(diatonic_chord).figure
        else:  # output == "xml"
            diatonic_chord_stream = stream.Stream()
            diatonic_chord_stream.append(diatonic_chord)
            diatonic_chord_figure = diatonic_chord_stream
            diatonic_chord_figure = m21_to_base64(diatonic_chord_figure)

        if diatonic_chord_figure not in answer_list:
            answer_list.append(diatonic_chord_figure)

        while len(answer_list) != 4:
            random_scale_degree = random.randrange(1, len(current_scale), 1)
            random_quality = random.choice(["", "m", "+", "dim"])
            another_wrong_chord = call_question_function("chord", user_level, {"0": [current_scale[random_scale_degree]], "1": [random_quality], "2": False})

            if output == "string":
                another_wrong_chord_figure = harmony.chordSymbolFromChord(another_wrong_chord).figure
            else:  # output == "xml"
                another_wrong_chord_stream = stream.Stream()
                another_wrong_chord_stream.append(another_wrong_chord)
                another_wrong_chord_figure = another_wrong_chord_stream
                another_wrong_chord_figure = m21_to_base64(another_wrong_chord_figure)

            if len(set(another_wrong_chord.pitchNames).intersection(set([p.name for p in current_scale]))) != len(another_wrong_chord.pitchNames):
                if another_wrong_chord_figure not in answer_list:
                    answer_list.append(another_wrong_chord_figure)

        random.shuffle(answer_list)
        correct_answer_index = answer_list.index(correct_answer) + 1

        return answer_list, correct_answer_index
    
