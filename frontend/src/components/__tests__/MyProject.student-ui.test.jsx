import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchMyBoard:vi.fn(), updateBoard:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
vi.mock('../KanbanBoard.jsx',()=>({default:({board,canEdit})=><div data-testid="kanban">KANBAN-{board.id}-{String(canEdit)}</div>}));
vi.mock('../ProjectWorkflowView.jsx',()=>({default:({projectBoardId})=><div data-testid="workflow">WORKFLOW-{projectBoardId}</div>}));
vi.mock('../GitLabPanel.jsx',()=>({default:({boardId,canManage})=><div data-testid="gitlab">GITLAB-{boardId}-{String(canManage)}</div>}));
import MyProject from '../MyProject.jsx';

const board={id:7,title:'Portal',github_repo:'https://github.com/spu/portal'};
beforeEach(()=>{ vi.clearAllMocks(); delete window.myProjectSetActiveTab; delete window.__myProjectActiveTab; api.fetchMyBoard.mockResolvedValue({data:{has_project:true,board}}); api.updateBoard.mockResolvedValue({data:{...board,github_repo:'https://github.com/new/repo'}}); vi.spyOn(window,'alert').mockImplementation(()=>{}); });

describe('MyProject student workspace contract',()=>{
  it('shows loading state',()=>{ api.fetchMyBoard.mockReturnValue(new Promise(()=>{})); render(<MyProject/>); expect(screen.getByText('جاري تحميل لوحة مشروعك…')).toBeTruthy(); });
  it('loads active project board',async()=>{ render(<MyProject/>); expect(await screen.findByText('مشروعي')).toBeTruthy(); expect(api.fetchMyBoard).toHaveBeenCalledOnce(); });
  it('shows load error',async()=>{ api.fetchMyBoard.mockRejectedValue(new Error('x')); render(<MyProject/>); expect(await screen.findByText('Failed to load board.')).toBeTruthy(); });
  it('shows no-project empty state',async()=>{ api.fetchMyBoard.mockResolvedValue({data:{has_project:false}}); render(<MyProject/>); expect(await screen.findByText('لا يوجد مشروع نشط')).toBeTruthy(); });
  it('shows approval guidance without project',async()=>{ api.fetchMyBoard.mockResolvedValue({data:{has_project:false}}); render(<MyProject/>); expect(await screen.findByText(/بمجرد موافقة رئيس القسم/)).toBeTruthy(); });
  it.each(['Board','Workflow','GitLab'])('renders tab %s',async(label)=>{ render(<MyProject/>); expect(await screen.findByRole('button',{name:label})).toBeTruthy(); });
  it('starts on board tab',async()=>{ render(<MyProject/>); expect((await screen.findByTestId('kanban')).textContent).toContain('KANBAN-7-true'); expect(screen.queryByTestId('workflow')).toBeNull(); });
  it('switches to workflow tab',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); fireEvent.click(screen.getByRole('button',{name:'Workflow'})); expect(screen.getByTestId('workflow').textContent).toContain('WORKFLOW-7'); });
  it('switches to GitLab tab with read-only management flag',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); fireEvent.click(screen.getByRole('button',{name:'GitLab'})); expect(screen.getByTestId('gitlab').textContent).toContain('GITLAB-7-false'); });
  it('switches back to board',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); fireEvent.click(screen.getByRole('button',{name:'Workflow'})); fireEvent.click(screen.getByRole('button',{name:'Board'})); expect(screen.getByTestId('kanban')).toBeTruthy(); });
  it('publishes global tab callback',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); expect(typeof window.myProjectSetActiveTab).toBe('function'); });
  it('publishes initial global active tab',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); expect(window.__myProjectActiveTab).toBe('board'); });
  it('global callback can open workflow',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); window.myProjectSetActiveTab('workflow'); await waitFor(()=>expect(screen.getByTestId('workflow')).toBeTruthy()); expect(window.__myProjectActiveTab).toBe('workflow'); });
  it('global callback can open GitLab',async()=>{ render(<MyProject/>); await screen.findByTestId('kanban'); window.myProjectSetActiveTab('gitlab'); await waitFor(()=>expect(screen.getByTestId('gitlab')).toBeTruthy()); });
  it('removes global callback on unmount',async()=>{ const view=render(<MyProject/>); await screen.findByTestId('kanban'); view.unmount(); expect(window.myProjectSetActiveTab).toBeUndefined(); });
  it('shows existing repository as external link',async()=>{ render(<MyProject/>); const link=await screen.findByRole('link',{name:'https://github.com/spu/portal'}); expect(link.getAttribute('href')).toBe('https://github.com/spu/portal'); expect(link.getAttribute('target')).toBe('_blank'); expect(link.getAttribute('rel')).toBe('noreferrer'); });
  it('shows empty repository message',async()=>{ api.fetchMyBoard.mockResolvedValue({data:{has_project:true,board:{...board,github_repo:''}}}); render(<MyProject/>); expect(await screen.findByText('لا يوجد مستودع GitHub مربوط')).toBeTruthy(); });
  it('opens repository editor',async()=>{ render(<MyProject/>); fireEvent.click(await screen.findByTitle('تعديل رابط مستودع GitHub')); expect(screen.getByPlaceholderText('https://github.com/username/repo').value).toBe(board.github_repo); });
  it('opens empty repository editor with blank value',async()=>{ api.fetchMyBoard.mockResolvedValue({data:{has_project:true,board:{...board,github_repo:''}}}); render(<MyProject/>); fireEvent.click(await screen.findByTitle('تعديل رابط مستودع GitHub')); expect(screen.getByPlaceholderText('https://github.com/username/repo').value).toBe(''); });
  it('updates repository URL',async()=>{ render(<MyProject/>); fireEvent.click(await screen.findByTitle('تعديل رابط مستودع GitHub')); const input=screen.getByPlaceholderText('https://github.com/username/repo'); fireEvent.change(input,{target:{value:'https://github.com/new/repo'}}); fireEvent.click(input.parentElement.querySelector('button')); await waitFor(()=>expect(api.updateBoard).toHaveBeenCalledWith(7,{github_repo:'https://github.com/new/repo'})); expect(await screen.findByRole('link',{name:'https://github.com/new/repo'})).toBeTruthy(); });
  it('cancels repository edit and restores original URL',async()=>{ render(<MyProject/>); fireEvent.click(await screen.findByTitle('تعديل رابط مستودع GitHub')); const input=screen.getByPlaceholderText('https://github.com/username/repo'); fireEvent.change(input,{target:{value:'https://bad'}}); const buttons=input.parentElement.querySelectorAll('button'); fireEvent.click(buttons[1]); expect(screen.getByRole('link',{name:board.github_repo})).toBeTruthy(); });
  it('disables repository controls while saving',async()=>{ api.updateBoard.mockReturnValue(new Promise(()=>{})); render(<MyProject/>); fireEvent.click(await screen.findByTitle('تعديل رابط مستودع GitHub')); const input=screen.getByPlaceholderText('https://github.com/username/repo'); const buttons=input.parentElement.querySelectorAll('button'); fireEvent.click(buttons[0]); await waitFor(()=>expect(input.disabled).toBe(true)); expect(buttons[0].disabled).toBe(true); expect(buttons[1].disabled).toBe(true); });
  it('alerts and keeps editor after repository update failure',async()=>{ api.updateBoard.mockRejectedValue(new Error('x')); render(<MyProject/>); fireEvent.click(await screen.findByTitle('تعديل رابط مستودع GitHub')); const input=screen.getByPlaceholderText('https://github.com/username/repo'); fireEvent.click(input.parentElement.querySelector('button')); await waitFor(()=>expect(window.alert).toHaveBeenCalledWith('فشل تحديث رابط مستودع GitHub')); expect(screen.getByPlaceholderText('https://github.com/username/repo')).toBeTruthy(); });
  it('does not render workspace tabs without active project',async()=>{ api.fetchMyBoard.mockResolvedValue({data:{has_project:false}}); render(<MyProject/>); await screen.findByText('لا يوجد مشروع نشط'); expect(screen.queryByRole('button',{name:'Board'})).toBeNull(); });
  it('does not render GitHub editor during loading',()=>{ api.fetchMyBoard.mockReturnValue(new Promise(()=>{})); render(<MyProject/>); expect(screen.queryByTitle('تعديل رابط مستودع GitHub')).toBeNull(); });
});
