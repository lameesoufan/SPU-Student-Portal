import {
  UserPlus,
  CheckCircle,
  Clock,
  Info,
} from 'lucide-react';

export function NotifIcon({ type }) {
  const map = {
    invitation: UserPlus,
    update: CheckCircle,
    reminder: Clock,
    info: Info,
  };
  const Comp = map[type] || Info;
  return <Comp size={16} />;
}

export function notifBgColor(type) {
  const map = {
    invitation: 'rgba(99,102,241,0.15)',
    update: 'rgba(16,185,129,0.15)',
    reminder: 'rgba(245,158,11,0.15)',
  };
  return map[type] || 'rgba(100,116,139,0.15)';
}

export function notifTextColor(type) {
  const map = {
    invitation: '#6366f1',
    update: '#10b981',
    reminder: '#f59e0b',
  };
  return map[type] || '#64748b';
}