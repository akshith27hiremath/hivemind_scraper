"""Teacher-Student Classification Filter Module.

This module provides a teacher-student approach to classifying financial news headlines
into three categories:
- FACTUAL: Hard news with verifiable facts (earnings, mergers, events)
- OPINION: Analysis, commentary, predictions
- SLOP: Low-value clickbait, listicles, vague teasers

Usage:
    from mechanical_refinery.teacher_student import TeacherStudentFilter, TeacherLabeler

    # For inference (after training)
    filter = TeacherStudentFilter(model_path='path/to/model')
    results = filter.batch_classify(articles)

    # For labeling training data
    labeler = TeacherLabeler(provider='openai')
    labels = labeler.label_batch(articles)
"""

from .filter import TeacherStudentFilter, ClassificationResult
from .teacher_labeler import TeacherLabeler, TeacherLabel
from .student_classifier import StudentClassifier

__all__ = [
    'TeacherStudentFilter',
    'ClassificationResult',
    'TeacherLabeler',
    'TeacherLabel',
    'StudentClassifier',
]
