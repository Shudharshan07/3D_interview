import base64
import requests
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
import io
from rest_framework.views import APIView
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.platypus import HRFlowable

from .models import Interview, Question
from .serializers import InterviewSerializer, InterviewCreateSerializer, AnswerSubmissionSerializer, QuestionSerializer
from .services import InterviewService, QuestionService

class InterviewViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Interview.objects.all()
    serializer_class = InterviewSerializer
    lookup_field = 'id'

    def create(self, request):
        """
        POST /api/interviews/
        Accepts JD (text or file) and Resume (PDF or text).
        """
        jd_text = request.data.get('jd_text', '')
        resume_text = request.data.get('resume_text', '')
        
        # Check files
        jd_file = request.FILES.get('jd_file')
        resume_file = request.FILES.get('resume_file')
        
        print(f"--- Interview Create Request ---")
        print(f"JD File: {jd_file.name if jd_file else 'None'}")
        print(f"Resume File: {resume_file.name if resume_file else 'None'}")
        print(f"JD Text (Initial): {len(jd_text)} chars")
        print(f"Resume Text (Initial): {len(resume_text)} chars")

        if jd_file:
            content = jd_file.read()
            jd_text = content.decode('utf-8', errors='ignore')
            print(f"JD Text (After File): {len(jd_text)} chars")
            
        if resume_file:
            if resume_file.name.endswith('.pdf'):
                from pypdf import PdfReader
                reader = PdfReader(resume_file)
                extracted_text = ""
                for page in reader.pages:
                    extracted_text += page.extract_text() or ""
                resume_text = extracted_text
                print(f"Resume Text (After PDF Extraction): {len(resume_text)} chars")
            else:
                resume_text = resume_file.read().decode('utf-8', errors='ignore')
                print(f"Resume Text (After File): {len(resume_text)} chars")

        if not jd_text.strip() or not resume_text.strip():
            print(f"Validation FAILED: JD={bool(jd_text.strip())}, Resume={bool(resume_text.strip())}")
            return Response({"error": "Both JD and Resume are required."}, status=status.HTTP_400_BAD_REQUEST)
        interview = InterviewService.create_interview(jd_text, resume_text)
        return Response(InterviewSerializer(interview).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def report(self, request, id=None):
        """
        GET /api/interviews/{uuid}/report/
        Returns summary feedback and aggregate score.
        """
        report = InterviewService.get_interview_report(id)
        if report:
            return Response(report, status=status.HTTP_200_OK)
        return Response({"error": "Interview not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def pdf(self, request, id=None):
        """
        GET /api/interviews/{uuid}/pdf/
        Returns a detailed PDF report.
        """
        try:
            report_data = InterviewService.get_interview_report(id)
            if not report_data:
                return Response({"error": "Interview not found"}, status=status.HTTP_404_NOT_FOUND)

            interview = Interview.objects.get(id=id)
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter,
                    rightMargin=72, leftMargin=72,
                    topMargin=72, bottomMargin=18)
            
            styles = getSampleStyleSheet()
            
            title_style = styles['Heading1']
            title_style.alignment = 1
            heading_style = styles['Heading2']
            
            question_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontName='Helvetica-Bold',
                spaceAfter=6
            )
            
            answer_style = ParagraphStyle(
                'Answer',
                parent=styles['Normal'],
                fontName='Helvetica',
                textColor=colors.darkblue,
                leftIndent=10,
                spaceAfter=6
            )
            
            feedback_style = ParagraphStyle(
                'Feedback',
                parent=styles['Normal'],
                fontName='Helvetica-Oblique',
                textColor=colors.black,
                leftIndent=10,
                spaceAfter=12
            )

            flowables = []
            
            flowables.append(Paragraph("AI Interview Evaluation Report", title_style))
            flowables.append(Spacer(1, 12))
            
            flowables.append(Paragraph(f"Aggregate Score: {report_data.get('aggregate_score', 0)}/10", heading_style))
            flowables.append(Spacer(1, 12))
                
            flowables.append(Paragraph("Detailed Breakdown", heading_style))
            flowables.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=12))

            questions = interview.questions.all().order_by('sequence_order')
            for q in questions:
                # Remove emojis and unprintable chars by encoding to ascii
                clean_q_text = q.question_text.encode('ascii', 'ignore').decode('ascii')
                flowables.append(Paragraph(f"Q{q.sequence_order}: {clean_q_text}", question_style))
                
                ans_text = q.user_answer if q.user_answer else "No response provided."
                if ans_text == "[Answer provided via Whiteboard Diagram]":
                     ans_text = "Answer provided via Whiteboard Diagram."
                clean_ans_text = ans_text.encode('ascii', 'ignore').decode('ascii')
                flowables.append(Paragraph(f"Answer: {clean_ans_text}", answer_style))
                
                if q.status == 'EVALUATED':
                    score = q.score if q.score else 0
                    fb = q.feedback_text if q.feedback_text else ""
                    clean_fb = fb.encode('ascii', 'ignore').decode('ascii')
                    flowables.append(Paragraph(f"Score: {score}/10 | Feedback: {clean_fb}", feedback_style))
                else:
                    flowables.append(Paragraph(f"Status: {q.get_status_display()}", feedback_style))
                    
                flowables.append(Spacer(1, 12))
                
            doc.build(flowables)
            buffer.seek(0)
            
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="interview_report_{interview.id}.pdf"'
            return response
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InternalBridgeView(APIView):
    """
    POST /api/internal/submit-answer/
    The Bridge API for the Go service.
    """
    def post(self, request):
        serializer = AnswerSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            question = QuestionService.submit_answer(
                serializer.validated_data['question_id'],
                serializer.validated_data['answer'],
                serializer.validated_data.get('whiteboard_data')
            )
            if question:
                return Response(QuestionSerializer(question).data, status=status.HTTP_200_OK)
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SpeakView(APIView):
    """
    POST /api/speak/
    TTS using Sarvam AI.
    """
    def post(self, request):
        text = request.data.get('text', '')
        if not text:
            return Response({"error": "Text is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not settings.SARVAM_API_KEY:
             return Response({"error": "Sarvam API Key not configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            response = requests.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": settings.SARVAM_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "voice": "shubh",
                    "model": "bulbul:v3",
                    "language": "en-IN",
                },
                timeout=60,
            )
            
            if not response.ok:
                 return Response({"error": f"Sarvam API error: {response.status_code}"}, status=status.HTTP_502_BAD_GATEWAY)

            data = response.json()
            audio_base64 = data["audios"][0]
            audio_bytes = base64.b64decode(audio_base64)
            
            return HttpResponse(audio_bytes, content_type="audio/wav")
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
