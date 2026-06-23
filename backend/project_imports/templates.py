from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .constants import REQUIRED_HEADERS, VALID_DEPARTMENTS, VALID_PROJECT_TYPES


class TemplateGenerator:
    def generate_template(self):
        workbook = Workbook()
        projects = workbook.active
        projects.title = 'Projects'
        self._create_projects_sheet(projects)
        self._create_instructions_sheet(workbook)

        output = BytesIO()
        workbook.save(output)
        workbook.close()
        output.seek(0)
        return output.getvalue()

    def _create_projects_sheet(self, worksheet):
        worksheet.append(REQUIRED_HEADERS)
        worksheet.append([
            'محمد أحمد',
            '20250001',
            'نظام إدارة مشاريع التخرج',
            'software_engineering',
            'dr_ali',
            'graduation_1',
            'https://github.com/example/spu-project',
        ])
        worksheet.append([
            'سارة خالد',
            '20250002',
            'تحليل ذكي للبيانات الجامعية',
            'artificial_intelligence',
            'dr_sara',
            'graduation_2',
            '',
        ])

        header_fill = PatternFill('solid', fgColor='E0E7FF')
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')

        for column_idx in range(1, len(REQUIRED_HEADERS) + 1):
            worksheet.column_dimensions[get_column_letter(column_idx)].width = 24

        worksheet.freeze_panes = 'A2'
        worksheet.sheet_view.rightToLeft = True

    def _create_instructions_sheet(self, workbook):
        worksheet = workbook.create_sheet('Instructions')
        worksheet.sheet_view.rightToLeft = True
        rows = [
            ['Field', 'Description'],
            ['اسم الطالب', 'Full student name. It will be split into first and last name.'],
            ['الرقم الجامعي', 'Student university ID. This becomes the student username.'],
            ['اسم المشروع', 'Project title. Maximum 255 characters.'],
            ['مجال المشروع', f"One of: {', '.join(VALID_DEPARTMENTS)}"],
            ['اسم المشرف', 'Doctor username or unique full/partial doctor name.'],
            ['نمط المشروع', f"One of: {', '.join(VALID_PROJECT_TYPES)}"],
            ['رابط الـ Git', 'Optional GitHub or GitLab URL.'],
        ]
        for row in rows:
            worksheet.append(row)
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='DCFCE7')
        worksheet.column_dimensions['A'].width = 24
        worksheet.column_dimensions['B'].width = 90
