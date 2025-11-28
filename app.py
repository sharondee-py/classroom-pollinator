from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import random
import string
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app)

# Store active quizzes
quizzes = {}
student_progress = {}


def generate_quiz_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


@app.route('/')
def teacher_dashboard():
    return render_template('teacher.html')


@app.route('/student')
def student_dashboard():
    return render_template('student.html')


@app.route('/quiz/<quiz_code>')
def take_quiz(quiz_code):
    return render_template('take_quiz.html', quiz_code=quiz_code)


@socketio.on('create_quiz')
def handle_create_quiz(data):
    quiz_code = generate_quiz_code()

    quizzes[quiz_code] = {
        'title': data.get('title', 'Classroom Quiz'),
        'questions': data['questions'],
        'created_at': datetime.now().isoformat(),
        'teacher_id': request.sid
    }

    emit('quiz_created', {
        'quiz_code': quiz_code,
        'share_url': f'/quiz/{quiz_code}'
    }, room=request.sid)


@socketio.on('join_quiz')
def handle_join_quiz(data):
    quiz_code = data['quiz_code']
    student_id = request.sid

    if quiz_code in quizzes:
        join_room(quiz_code)

        # Initialize student progress
        if quiz_code not in student_progress:
            student_progress[quiz_code] = {}

        student_progress[quiz_code][student_id] = {
            'current_question': 0,
            'score': 0,
            'answers': [],
            'completed': False
        }

        quiz = quizzes[quiz_code]
        emit('quiz_started', {
            'title': quiz['title'],
            'total_questions': len(quiz['questions']),
            'first_question': quiz['questions'][0]
        }, room=request.sid)


@socketio.on('submit_answer')
def handle_submit_answer(data):
    quiz_code = data['quiz_code']
    question_index = data['question_index']
    answer_index = data['answer_index']
    student_id = request.sid

    if quiz_code in quizzes and quiz_code in student_progress:
        quiz = quizzes[quiz_code]
        question = quiz['questions'][question_index]

        # Check if answer is correct
        is_correct = (answer_index == question['correct_answer'])

        # Update student progress
        student_progress[quiz_code][student_id]['answers'].append({
            'question_index': question_index,
            'answer_index': answer_index,
            'is_correct': is_correct,
            'timestamp': datetime.now().isoformat()
        })

        if is_correct:
            student_progress[quiz_code][student_id]['score'] += 1

        # Move to next question or complete
        current_progress = student_progress[quiz_code][student_id]
        next_question_index = question_index + 1

        if next_question_index < len(quiz['questions']):
            student_progress[quiz_code][student_id]['current_question'] = next_question_index
            next_question = quiz['questions'][next_question_index]

            emit('next_question', {
                'question': next_question,
                'question_number': next_question_index + 1,
                'total_questions': len(quiz['questions']),
                'score': current_progress['score']
            }, room=request.sid)
        else:
            # Quiz completed
            student_progress[quiz_code][student_id]['completed'] = True
            final_score = current_progress['score']
            total_questions = len(quiz['questions'])

            emit('quiz_completed', {
                'score': final_score,
                'total_questions': total_questions,
                'percentage': (final_score / total_questions) * 100
            }, room=request.sid)

        # Send immediate feedback
        emit('answer_feedback', {
            'is_correct': is_correct,
            'correct_answer': question['correct_answer'],
            'explanation': question['explanation'],
            'your_answer': answer_index
        }, room=request.sid)


@socketio.on('get_quiz_results')
def handle_get_results(data):
    quiz_code = data['quiz_code']
    if quiz_code in student_progress:
        results = student_progress[quiz_code]
        emit('quiz_results', {
            'results': results,
            'total_students': len(results)
        }, room=request.sid)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)