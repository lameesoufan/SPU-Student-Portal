import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchMyInvitations:vi.fn(), respondToInvitation:vi.fn(), fetchMyProposalInvitations:vi.fn(), respondToProposalInvitation:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import MyInvitations from '../MyInvitations.jsx';

const ideaInv = { id:11, doctor_name:'Dr Ada', idea_title:'Doctor Idea', leader_name:'Student Leader' };
const propInv = { id:22, idea_title:'Student Proposal', leader_name:'Proposal Leader' };

beforeEach(()=>{
  vi.clearAllMocks();
  api.fetchMyInvitations.mockResolvedValue({data:[ideaInv]});
  api.fetchMyProposalInvitations.mockResolvedValue({data:[propInv]});
  api.respondToInvitation.mockResolvedValue({data:{}});
  api.respondToProposalInvitation.mockResolvedValue({data:{}});
  vi.spyOn(window,'prompt').mockReturnValue('Not a fit');
});

function ideaCard(){ return screen.getByText('Doctor Idea').parentElement.parentElement; }
function propCard(){ return screen.getByText('Student Proposal').parentElement.parentElement; }

describe('MyInvitations student team contract',()=>{
  it('renders heading',async()=>{ render(<MyInvitations/>); expect(await screen.findByRole('heading',{name:'دعوات الفريق'})).toBeTruthy(); });
  it('loads both invitation sources',async()=>{ render(<MyInvitations/>); await screen.findByText('Doctor Idea'); expect(api.fetchMyInvitations).toHaveBeenCalledOnce(); expect(api.fetchMyProposalInvitations).toHaveBeenCalledOnce(); });
  it('shows loader while both requests are pending',()=>{ api.fetchMyInvitations.mockReturnValue(new Promise(()=>{})); api.fetchMyProposalInvitations.mockReturnValue(new Promise(()=>{})); render(<MyInvitations/>); expect(document.querySelector('.spinner-dark')).toBeTruthy(); });
  it('shows shared load error if either request rejects',async()=>{ api.fetchMyInvitations.mockRejectedValue(new Error('x')); render(<MyInvitations/>); expect(await screen.findByText('Failed to load invitations.')).toBeTruthy(); });
  it('shows empty state when both lists empty',async()=>{ api.fetchMyInvitations.mockResolvedValue({data:[]}); api.fetchMyProposalInvitations.mockResolvedValue({data:[]}); render(<MyInvitations/>); expect(await screen.findByText('لا توجد دعوات معلقة')).toBeTruthy(); });
  it('shows caught-up copy in empty state',async()=>{ api.fetchMyInvitations.mockResolvedValue({data:[]}); api.fetchMyProposalInvitations.mockResolvedValue({data:[]}); render(<MyInvitations/>); expect(await screen.findByText("You're all caught up!")).toBeTruthy(); });
  it.each(['Doctor Idea Applications','Student Proposal Teams'])('shows invitation section %s',async(label)=>{ render(<MyInvitations/>); expect(await screen.findByText(label)).toBeTruthy(); });
  it.each(['Dr Ada','Doctor Idea','Student Leader','Student Proposal','Proposal Leader'])('shows invitation metadata %s',async(text)=>{ render(<MyInvitations/>); expect(await screen.findByText(text)).toBeTruthy(); });
  it('renders two accept actions',async()=>{ render(<MyInvitations/>); await screen.findByText('Doctor Idea'); expect(screen.getAllByRole('button',{name:/قبول/})).toHaveLength(2); });
  it('renders two reject actions',async()=>{ render(<MyInvitations/>); await screen.findByText('Doctor Idea'); expect(screen.getAllByRole('button',{name:/رفض/})).toHaveLength(2); });
  it('accepts doctor-idea invitation',async()=>{ render(<MyInvitations/>); await screen.findByText('Doctor Idea'); fireEvent.click(within(ideaCard()).getByRole('button',{name:/قبول/})); await waitFor(()=>expect(api.respondToInvitation).toHaveBeenCalledWith(11,'accept')); await waitFor(()=>expect(screen.queryByText('Doctor Idea')).toBeNull()); });
  it('rejects doctor-idea invitation',async()=>{ render(<MyInvitations/>); await screen.findByText('Doctor Idea'); fireEvent.click(within(ideaCard()).getByRole('button',{name:/رفض/})); await waitFor(()=>expect(api.respondToInvitation).toHaveBeenCalledWith(11,'reject')); });
  it('accepts proposal invitation with blank reason',async()=>{ render(<MyInvitations/>); await screen.findByText('Student Proposal'); fireEvent.click(within(propCard()).getByRole('button',{name:/قبول/})); await waitFor(()=>expect(api.respondToProposalInvitation).toHaveBeenCalledWith(22,'accept','')); });
  it('rejects proposal invitation with prompted reason',async()=>{ render(<MyInvitations/>); await screen.findByText('Student Proposal'); fireEvent.click(within(propCard()).getByRole('button',{name:/رفض/})); await waitFor(()=>expect(api.respondToProposalInvitation).toHaveBeenCalledWith(22,'reject','Not a fit')); });
  it('uses blank reason when prompt is cancelled',async()=>{ window.prompt.mockReturnValue(null); render(<MyInvitations/>); await screen.findByText('Student Proposal'); fireEvent.click(within(propCard()).getByRole('button',{name:/رفض/})); await waitFor(()=>expect(api.respondToProposalInvitation).toHaveBeenCalledWith(22,'reject','')); });
  it('removes accepted proposal card after success',async()=>{ render(<MyInvitations/>); await screen.findByText('Student Proposal'); fireEvent.click(within(propCard()).getByRole('button',{name:/قبول/})); await waitFor(()=>expect(screen.queryByText('Student Proposal')).toBeNull()); expect(screen.getByText('Doctor Idea')).toBeTruthy(); });
  it('keeps doctor invitation when action fails',async()=>{ api.respondToInvitation.mockRejectedValue({response:{data:{error:'DENIED'}}}); render(<MyInvitations/>); await screen.findByText('Doctor Idea'); fireEvent.click(within(ideaCard()).getByRole('button',{name:/قبول/})); expect(await screen.findByText('DENIED')).toBeTruthy(); expect(screen.getByText('Doctor Idea')).toBeTruthy(); });
  it('keeps proposal invitation when action fails',async()=>{ api.respondToProposalInvitation.mockRejectedValue({response:{data:{error:'PROP DENIED'}}}); render(<MyInvitations/>); await screen.findByText('Student Proposal'); fireEvent.click(within(propCard()).getByRole('button',{name:/قبول/})); expect(await screen.findByText('PROP DENIED')).toBeTruthy(); expect(screen.getByText('Student Proposal')).toBeTruthy(); });
  it('uses generic doctor action error',async()=>{ api.respondToInvitation.mockRejectedValue(new Error('x')); render(<MyInvitations/>); await screen.findByText('Doctor Idea'); fireEvent.click(within(ideaCard()).getByRole('button',{name:/قبول/})); expect(await screen.findByText('Something went wrong.')).toBeTruthy(); });
  it('uses generic proposal action error',async()=>{ api.respondToProposalInvitation.mockRejectedValue(new Error('x')); render(<MyInvitations/>); await screen.findByText('Student Proposal'); fireEvent.click(within(propCard()).getByRole('button',{name:/قبول/})); expect(await screen.findByText('Something went wrong.')).toBeTruthy(); });
  it('does not render doctor section when only proposals exist',async()=>{ api.fetchMyInvitations.mockResolvedValue({data:[]}); render(<MyInvitations/>); await screen.findByText('Student Proposal'); expect(screen.queryByText('Doctor Idea Applications')).toBeNull(); });
  it('does not render proposal section when only doctor invitations exist',async()=>{ api.fetchMyProposalInvitations.mockResolvedValue({data:[]}); render(<MyInvitations/>); await screen.findByText('Doctor Idea'); expect(screen.queryByText('Student Proposal Teams')).toBeNull(); });
  it.each(['قبول الدعوة يعني أنك لن تتمكن من التقدم لمكان آخر حتى يُبت في هذا الطلب. وفي حال الرفض، ستصبح حراً مرة أخرى.','قبول الدعوة يعني أنك لن تتمكن من التقدم لمكان آخر حتى يُبت في هذا المقترح. وفي حال الرفض، ستصبح حراً مرة أخرى.'])('shows lockout notice %s',async(text)=>{ render(<MyInvitations/>); expect(await screen.findByText(text)).toBeTruthy(); });
  it('disables doctor invitation actions while request is pending',async()=>{ api.respondToInvitation.mockReturnValue(new Promise(()=>{})); render(<MyInvitations/>); await screen.findByText('Doctor Idea'); const buttons=within(ideaCard()).getAllByRole('button'); fireEvent.click(buttons[0]); await waitFor(()=>expect(buttons.every(b=>b.disabled)).toBe(true)); });
  it('disables proposal invitation actions while request is pending',async()=>{ api.respondToProposalInvitation.mockReturnValue(new Promise(()=>{})); render(<MyInvitations/>); await screen.findByText('Student Proposal'); const buttons=within(propCard()).getAllByRole('button'); fireEvent.click(buttons[0]); await waitFor(()=>expect(buttons.every(b=>b.disabled)).toBe(true)); });
});
