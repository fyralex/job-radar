import {useEffect} from 'react';
import {BoardsEditor} from './components/BoardsEditor';
import {PostingsTab} from './components/PostingsTab';
import {ProfilesEditor} from './components/ProfilesEditor';
import {SearchSettingsForm} from './components/SearchSettingsForm';
import {useLocalPreference} from './hooks/useLocalPreference';
import {useRecordVisitMutation} from './redux/api';

type Tab = 'postings' | 'settings';
const TABS: {key: Tab; label: string}[] = [
  {key: 'postings', label: 'Postings'},
  {key: 'settings', label: 'Settings'},
];

export function App() {
  const [tab, setTab] = useLocalPreference<Tab>('jobradar.tab', 'postings');
  const [recordVisit] = useRecordVisitMutation();

  // One visit per page load: postings first seen after the previous visit get
  // a "New" badge.
  useEffect(() => {
    void recordVisit();
  }, [recordVisit]);

  return (
    <div className="app">
      <header className="header">
        <h1>Job Radar</h1>
        <nav className="tabs" role="tablist" aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              className={tab === t.key ? 'tab active' : 'tab'}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {tab === 'postings' ? (
          <PostingsTab onOpenSettings={() => setTab('settings')} />
        ) : (
          <>
            <ProfilesEditor />
            <SearchSettingsForm />
            <BoardsEditor />
          </>
        )}
      </main>
    </div>
  );
}
