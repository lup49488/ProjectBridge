import React from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

type Profile = { id: string; display_name: string; skills: Record<string, number>; interests: string[]; goals: string[]; weekly_hours: number | null; role_preference: string; communication: string; structure: string; revision: number }
type Requirement = { id: string; skill: string; aggregation: 'expert' | 'collaborative'; required_level?: number; target_capacity?: number; importance: number; critical: boolean }
type Project = { id: string; title: string; idea: string; desired_team_size: number; idea_revision: number; requirements: { interests: string[]; goals: string[]; weekly_hours_min: number; skill_requirements: Requirement[] } | null; requirements_revision: number; team_revision: number; member_ids: string[] }
type Revisions = { idea: number; requirements: number; team: number; profiles: number }
type Task = { id: string; title: string; definition_of_done: string; required_skill: string | null; required_level: number | null; owner_id: string | null; estimated_hours: number; status: 'todo' | 'doing' | 'done' }
type Roadmap = { id?: string; revision?: number; stale?: boolean; source?: string; draft_pending?: boolean; assumptions: string[]; milestones: { id?: string; week: number; title: string; objective: string; tasks: Task[] }[] }
type Page = 'home' | 'create' | 'requirements' | 'profiles' | 'team' | 'roadmap'

const EXAMPLE_TITLE = 'CS Club website'
const EXAMPLE_IDEA = 'I want to start a CS club and build a website where students can see meetings and projects. Club organizers need to edit the event list through a small content API. We can spend about three hours per person each week.'
const apiRequest = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    throw new Error(typeof detail === 'string' ? detail : detail?.message ?? `Request failed (${response.status})`)
  }
  return response.status === 204 ? undefined as T : response.json()
}
const revisionsFor = (project: Project, profilesRevision: number): Revisions => ({ idea: project.idea_revision, requirements: project.requirements_revision, team: project.team_revision, profiles: profilesRevision })
const navigate = (hash: string) => { window.location.hash = hash }
const projectHash = (page: 'requirements' | 'team' | 'roadmap', id: string) => `#/${page}/${id}`

function App() {
  const [page, setPage] = React.useState<Page>('home')
  const [projectId, setProjectId] = React.useState('')
  const [project, setProject] = React.useState<Project | null>(null)
  const [profiles, setProfiles] = React.useState<Profile[]>([])
  const [profilesRevision, setProfilesRevision] = React.useState(1)
  const [projects, setProjects] = React.useState<Project[]>([])
  const [matchData, setMatchData] = React.useState<any>(null)
  const [roadmap, setRoadmap] = React.useState<Roadmap | null>(null)
  const [suggestion, setSuggestion] = React.useState<any>(null)
  const [notice, setNotice] = React.useState('')
  const [explanationBusy, setExplanationBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [ready, setReady] = React.useState(false)
  const [routeLoading, setRouteLoading] = React.useState(false)
  const routeSequence = React.useRef(0)

  const refreshBase = React.useCallback(async () => {
    const [profileResult, projectResult] = await Promise.all([
      apiRequest<{ profiles: Profile[]; profiles_revision: number }>('/profiles'),
      apiRequest<{ projects: Project[] }>('/projects'),
    ])
    setProfiles(profileResult.profiles); setProfilesRevision(profileResult.profiles_revision); setProjects(projectResult.projects)
  }, [])

  const loadProject = React.useCallback(async (id: string) => {
    const [projectResult, profileResult] = await Promise.all([
      apiRequest<{ project: Project }>(`/projects/${id}`),
      apiRequest<{ profiles: Profile[]; profiles_revision: number }>('/profiles'),
    ])
    setProject(projectResult.project); setProjectId(id); setProfiles(profileResult.profiles); setProfilesRevision(profileResult.profiles_revision)
    return { project: projectResult.project, profilesRevision: profileResult.profiles_revision }
  }, [])

  const loadRoute = React.useCallback(async () => {
    const sequence = ++routeSequence.current
    const parts = window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean)
    const next = (parts[0] as Page) || 'home'
    const hasProjectRoute = next === 'requirements' || next === 'team' || next === 'roadmap'
    setPage(['home', 'create', 'requirements', 'profiles', 'team', 'roadmap'].includes(next) ? next : 'home')
    setError(''); setNotice('')
    if (hasProjectRoute && !parts[1]) { setRouteLoading(false); navigate('#/'); return }
    setRouteLoading(hasProjectRoute)
    if (hasProjectRoute) setProjectId(parts[1])
    try {
    if (hasProjectRoute) {
      try {
        const loaded = await loadProject(parts[1])
        if (next === 'requirements') {
          const result = await apiRequest<any>(`/projects/${parts[1]}/analysis`, { method: 'POST', body: JSON.stringify({ expected_idea_revision: loaded.project.idea_revision }) })
          setMatchData(result)
        } else if (next === 'team') {
          if (!loaded.project.requirements) { navigate(projectHash('requirements', parts[1])); return }
          const result = await apiRequest<any>(`/projects/${parts[1]}/matches`)
          setMatchData(result); setSuggestion(null)
        } else {
          if (!loaded.project.requirements) { navigate(projectHash('requirements', parts[1])); return }
          const [matches, saved] = await Promise.all([
            apiRequest<any>(`/projects/${parts[1]}/matches`),
            apiRequest<{ data: Roadmap | null }>(`/projects/${parts[1]}/roadmap`),
          ])
          setMatchData(matches); setRoadmap(saved.data)
        }
      } catch (e) { setError((e as Error).message) }
    }
    try { await refreshBase(); setReady(true) } catch (e) { setError((e as Error).message) }
    } finally { if (sequence === routeSequence.current) setRouteLoading(false) }
  }, [loadProject, refreshBase])

  React.useEffect(() => {
    let active = true
    apiRequest('/demo/session', { method: 'POST' }).then(() => { if (active) return loadRoute() }).catch((e) => { if (active) { setError((e as Error).message); setReady(false) } })
    const onHash = () => { void loadRoute() }
    window.addEventListener('hashchange', onHash)
    return () => { active = false; window.removeEventListener('hashchange', onHash) }
  }, [loadRoute])

  const perform = async (action: () => Promise<void>) => { setBusy(true); setError(''); setNotice(''); try { await action() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }

  const createProject = (title: string, idea: string, size: number) => perform(async () => {
    const result = await apiRequest<{ project: Project }>('/projects', { method: 'POST', body: JSON.stringify({ client_request_id: crypto.randomUUID(), title, idea, desired_team_size: size }) })
    navigate(projectHash('requirements', result.project.id))
  })

  const saveRequirements = (requirements: NonNullable<Project['requirements']>) => project && perform(async () => {
    const result = await apiRequest<{ project: Project }>(`/projects/${project.id}/requirements`, { method: 'PUT', body: JSON.stringify({ expected_idea_revision: project.idea_revision, expected_requirements_revision: project.requirements_revision, requirements }) })
    setProject(result.project); setNotice('Requirements confirmed. Matching is ready.'); navigate(projectHash('team', project.id))
  })

  const refreshTeam = async () => {
    if (!project) return
    const result = await apiRequest<any>(`/projects/${project.id}/matches`)
    setMatchData(result); setProject((current) => current ? { ...current, team_revision: result.input_revisions.team, member_ids: current.member_ids } : current)
  }

  const saveTeam = (memberIds: string[]) => project && perform(async () => {
    const result = await apiRequest<any>(`/projects/${project.id}/team`, { method: 'PUT', body: JSON.stringify({ input_revisions: revisionsFor(project, profilesRevision), member_ids: memberIds }) })
    setProject(result.project); setMatchData({ data: result.data, input_revisions: result.input_revisions }); setSuggestion(null); setNotice('Team saved. You can draft the first roadmap.');
  })

  const saveRoadmap = (draft: Roadmap, source: string) => project && perform(async () => {
    const result = await apiRequest<{ data: Roadmap }>(`/projects/${project.id}/roadmap`, { method: 'PUT', body: JSON.stringify({ input_revisions: revisionsFor(project, profilesRevision), expected_roadmap_revision: roadmap?.id ? roadmap.revision : null, confirm_replace: Boolean(roadmap?.id), source, roadmap: { schema_version: '1.0', milestones: draft.milestones.map((m) => ({ week: m.week, title: m.title, objective: m.objective, tasks: m.tasks.map(({ id: _id, status: _status, ...task }) => task) })), assumptions: draft.assumptions } }) })
    setRoadmap(result.data); setNotice('Roadmap saved.')
  })

  const explainCandidate = async (candidateId: string): Promise<string | null> => {
    if (!project) return null
    setExplanationBusy(true); setError('')
    try {
      const result = await apiRequest<any>(`/projects/${project.id}/explanation`, { method: 'POST', body: JSON.stringify({ input_revisions: revisionsFor(project, profilesRevision), candidate_id: candidateId }) })
      return result.data?.summary ?? 'No eligible candidate is available to explain yet.'
    } catch (e) {
      setError((e as Error).message)
      return null
    } finally { setExplanationBusy(false) }
  }

  return <main className="shell app-shell">
    <nav className="nav"><a className="brand" href="#/"><span className="brand-mark">pb</span> projectbridge</a><div className="nav-links"><a href="#/profiles">Profiles</a><a href="#/">Projects</a></div><span className="demo-pill"><i /> Fictional demo</span></nav>
    {!ready && !error && !routeLoading && <div className="notice">Connecting to the local demo…</div>}
    {routeLoading && <div className="notice" role="status">Opening your project…</div>}
    {error && <div className="alert" role="alert">{error} <button className="quiet-button" onClick={() => void loadRoute()}>Retry</button></div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    {page === 'home' && <HomePage profiles={profiles} projects={projects} onCreate={() => navigate('#/create')} onOpen={(id) => navigate(projectHash('team', id))} />}
    {page === 'create' && <CreatePage busy={busy} onCreate={createProject} />}
    {page === 'requirements' && project?.id === projectId && <RequirementsPage project={project} draft={matchData?.data} generation={matchData?.generation} busy={busy} onSave={saveRequirements} />}
    {page === 'profiles' && <ProfilesPage profiles={profiles} onSave={(updated, revision) => perform(async () => {
      const result = await apiRequest<{ profile: Profile; profiles_revision: number }>(`/profiles/${updated.id}`, { method: 'PATCH', body: JSON.stringify({ expected_revision: revision, weekly_hours: updated.weekly_hours, role_preference: updated.role_preference, communication: updated.communication, structure: updated.structure }) })
      setProfiles((current) => current.map((p) => p.id === updated.id ? result.profile : p)); setProfilesRevision(result.profiles_revision); setNotice(`${result.profile.display_name}'s profile saved.`)
    })} busy={busy} />}
    {page === 'team' && project?.id === projectId && <TeamPage project={project} profiles={profiles} profileRevision={profilesRevision} data={matchData?.data} suggestion={suggestion} busy={busy || explanationBusy} onSuggest={() => perform(async () => { const result = await apiRequest<any>(`/projects/${project.id}/team/suggestion`, { method: 'POST', body: JSON.stringify({ input_revisions: revisionsFor(project, profilesRevision) }) }); setSuggestion(result.data) })} onExplain={explainCandidate} onSave={saveTeam} onRoadmap={() => navigate(projectHash('roadmap', project.id))} onRefresh={refreshTeam} />}
    {page === 'roadmap' && project?.id === projectId && <RoadmapPage project={project} profiles={profiles} profileRevision={profilesRevision} data={matchData?.data} roadmap={roadmap} busy={busy} onDraft={() => perform(async () => { const result = await apiRequest<any>(`/projects/${project.id}/roadmap/draft`, { method: 'POST', body: JSON.stringify({ input_revisions: revisionsFor(project, profilesRevision) }) }); setRoadmap({ ...result.data, id: roadmap?.id, revision: roadmap?.revision, stale: roadmap?.stale, draft_pending: true, source: result.generation.source }); setNotice('Editable draft generated. Review it before saving.') })} onSave={saveRoadmap} onTaskStatus={(task, status) => perform(async () => { const result = await apiRequest<any>(`/tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify({ expected_roadmap_revision: roadmap?.revision, status }) }); setRoadmap((current) => current ? { ...current, revision: result.roadmap_revision, milestones: current.milestones.map((m) => ({ ...m, tasks: m.tasks.map((t) => t.id === task.id ? { ...t, status } : t) })) } : current) })} />}
    <footer><a className="brand" href="#/"><span className="brand-mark">pb</span> projectbridge</a><span>Built for teams starting with an idea.</span><span className="footer-status">{ready ? 'API connected' : 'Fixture-first prototype'}</span></footer>
  </main>
}

function HomePage({ profiles, projects, onCreate, onOpen }: { profiles: Profile[]; projects: Project[]; onCreate: () => void; onOpen: (id: string) => void }) {
  return <><section className="hero" id="top"><div className="eyebrow"><span>✳</span> FROM FIRST IDEA TO FIRST TEAM</div><h1>Good ideas need<br /><em>the right mix.</em></h1><p className="intro">Find teammates who bring what your project is missing. See why they fit, choose your team, and make a plan together.</p><div className="hero-actions"><button className="button primary" onClick={onCreate}>Start a project <span>↘</span></button><span className="no-account">No account needed</span></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="art-core"><span>idea</span><b>✳</b><span>team</span></div><div className="satellite sat-a">✦</div><div className="satellite sat-b">↗</div><div className="satellite sat-c">●</div></div></section>
    <section className="steps" aria-label="How it works"><div><span>01</span><h2>Shape the idea</h2><p>Turn a spark into clear skills and needs.</p></div><div><span>02</span><h2>Find your mix</h2><p>See who fills a gap, with the reasons.</p></div><div><span>03</span><h2>Make a start</h2><p>Build a team and a first project plan.</p></div></section>
    <section className="demo"><div className="demo-head"><div><div className="eyebrow">YOUR DEMO WORKSPACE</div><h2>Projects &amp; people</h2></div><span className="status">● {profiles.length} fictional profiles</span></div><div className="demo-card"><div className="demo-copy"><span className="project-icon">⌘</span><h3>Start with a clear example</h3><p>Explore a fixture project from its requirements through a saved team and a four-week plan.</p><button className="text-link link-button" onClick={onCreate}>Create a project <span>↗</span></button></div><div className="people"><div className="people-label">RECENT PROJECTS <b>{projects.length} in this session</b></div>{projects.length ? projects.map((project) => <button className="project-row" key={project.id} onClick={() => onOpen(project.id)}><span className="project-icon small">⌘</span><span><b>{project.title}</b><small>{project.requirements ? 'Requirements confirmed' : 'Needs requirement review'}</small></span><span>↗</span></button>) : <p className="muted">Your new project will appear here.</p>}<a href="#/profiles" className="text-link">Browse fictional profiles <span>↗</span></a></div></div></section>
    <section className="engine"><div><div className="eyebrow">NOT A BLACK BOX</div><h2>Complementarity,<br /><em>you can see.</em></h2></div><p>Recommendations respond to the skills your current team is missing. The score is a transparent heuristic, never a prediction of success.</p></section></>
}

function CreatePage({ onCreate, busy }: { onCreate: (title: string, idea: string, size: number) => void; busy: boolean }) {
  const [title, setTitle] = React.useState(''); const [idea, setIdea] = React.useState(''); const [size, setSize] = React.useState(4)
  return <section className="workflow"><StepHeader step="01 / PROJECT IDEA" title="Start with the idea." description="Describe what you want to build. You will review every suggested requirement before it affects matching." /><div className="panel form-panel"><label>Project name<input value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Campus garden map" /></label><label>What would you like to make?<textarea value={idea} maxLength={2000} minLength={20} onChange={(e) => setIdea(e.target.value)} placeholder="Describe the goal, who it helps, and any important features…" rows={6} /></label><label>Target team size<select value={size} onChange={(e) => setSize(Number(e.target.value))}><option value={2}>2 people</option><option value={3}>3 people</option><option value={4}>4 people</option></select></label><div className="form-actions"><button className="button primary" disabled={busy || title.trim().length < 1 || idea.trim().length < 20} onClick={() => onCreate(title.trim(), idea.trim(), size)}>{busy ? 'Creating…' : 'Create and review needs'} <span>→</span></button><button className="quiet-button" onClick={() => { setTitle(EXAMPLE_TITLE); setIdea(EXAMPLE_IDEA); setSize(4) }}>Use CS Club example</button></div></div></section>
}

function RequirementsPage({ project, draft, generation, busy, onSave }: { project: Project; draft: any; generation: any; busy: boolean; onSave: (requirements: NonNullable<Project['requirements']>) => void }) {
  const [requirements, setRequirements] = React.useState<Requirement[]>([]); const [hours, setHours] = React.useState(3); const [interests, setInterests] = React.useState('web, education'); const [goals, setGoals] = React.useState('learn, help_school')
  React.useEffect(() => {
    if (draft?.roles?.length) setRequirements(draft.roles.flatMap((role: any) => role.skill_requirements.map((item: any) => ({ id: item.id, skill: item.skill, aggregation: item.aggregation, required_level: item.required_level ?? undefined, target_capacity: item.target_capacity ?? undefined, importance: item.importance, critical: Boolean(item.suggested_critical) }))))
    else setRequirements([{ id: 'manual-frontend', skill: 'react', aggregation: 'expert', required_level: 2, importance: .5, critical: false }, { id: 'manual-backend', skill: 'python', aggregation: 'expert', required_level: 2, importance: .5, critical: false }])
  }, [draft])
  const update = (index: number, change: Partial<Requirement>) => setRequirements((items) => items.map((item, i) => i === index ? { ...item, ...change } : item))
  return <section className="workflow"><StepHeader step="02 / REVIEW REQUIREMENTS" title="Make the needs explicit." description="Suggestions are a starting point. Edit skill levels, importance, and release-blocking flags before confirming." /><div className="panel"><div className="review-banner"><span className="project-icon small">⌘</span><div><b>{project.title}</b><small>{generation?.source === 'fixture' ? 'Exact CS Club example · deterministic fixture draft' : 'Template needs · please review and edit'}</small></div></div>{generation?.status === 'needs_input' && <p className="inline-note">This idea did not match the fixture, so these editable template requirements are not inferred from your text.</p>}<div className="field-grid"><label>Minimum hours per person / week<input type="number" min={1} max={10} value={hours} onChange={(e) => setHours(Number(e.target.value))} /></label><label>Interests (comma separated)<input value={interests} onChange={(e) => setInterests(e.target.value)} /></label><label>Goals (comma separated)<input value={goals} onChange={(e) => setGoals(e.target.value)} /></label></div><div className="requirement-list">{requirements.map((item, index) => <div className="requirement-row" key={item.id}><div><b>{item.skill.replaceAll('_', ' ')}</b><small>{item.aggregation === 'expert' ? 'Individual proficiency' : 'Shared team capacity'}</small></div>{item.aggregation === 'expert' ? <label>Level<select value={item.required_level} onChange={(e) => update(index, { required_level: Number(e.target.value) })}>{[1,2,3,4].map((level) => <option key={level} value={level}>{level}</option>)}</select></label> : <label>Capacity<input type="number" min={1} max={16} value={item.target_capacity} onChange={(e) => update(index, { target_capacity: Number(e.target.value) })} /></label>}<label>Importance<input type="number" min={0.01} max={1} step={0.05} value={item.importance} onChange={(e) => update(index, { importance: Number(e.target.value) })} /></label><label className="check-label"><input type="checkbox" checked={item.critical} onChange={(e) => update(index, { critical: e.target.checked })} /> Release-blocking</label></div>)}</div><button className="quiet-button" onClick={() => setRequirements((items) => [...items, { id: `manual-${crypto.randomUUID()}`, skill: 'writing', aggregation: 'expert', required_level: 2, importance: .1, critical: false }])}>+ Add writing requirement</button><div className="form-actions"><button className="button primary" disabled={busy || requirements.length === 0} onClick={() => onSave({ interests: interests.split(',').map((x) => x.trim()).filter(Boolean), goals: goals.split(',').map((x) => x.trim()).filter(Boolean), weekly_hours_min: hours, skill_requirements: requirements })}>Confirm reviewed requirements <span>→</span></button></div></div></section>
}

function ProfilesPage({ profiles, onSave, busy }: { profiles: Profile[]; busy: boolean; onSave: (profile: Profile, revision: number) => void }) {
  const [editing, setEditing] = React.useState<Profile | null>(null)
  return <section className="workflow"><StepHeader step="PEOPLE / FICTIONAL DEMO POOL" title="Meet the people." description="Profile details shape compatibility and availability. Changes are session-local and update matching revisions." /><div className="profile-grid">{profiles.map((profile, i) => <article className="profile-card" key={profile.id}><span className={`avatar avatar-${i % 4}`}>{profile.display_name[0]}</span><h3>{profile.display_name}</h3><p>{Object.entries(profile.skills).map(([skill, level]) => `${skill.replaceAll('_', ' ')} ${level}`).join(' · ')}</p><div className="tags">{profile.interests.slice(0, 2).map((interest) => <span key={interest}>{interest}</span>)}<span>{profile.weekly_hours ?? '—'} hrs / week</span></div><button className="quiet-button" onClick={() => setEditing(profile)}>Edit profile</button></article>)}</div>{editing && <ProfileEditor key={editing.id} profile={editing} busy={busy} onCancel={() => setEditing(null)} onSave={(updated) => { onSave(updated, editing.revision); setEditing(null) }} />}</section>
}

function ProfileEditor({ profile, busy, onCancel, onSave }: { profile: Profile; busy: boolean; onCancel: () => void; onSave: (profile: Profile) => void }) {
  const [hours, setHours] = React.useState(profile.weekly_hours ?? 0); const [role, setRole] = React.useState(profile.role_preference); const [communication, setCommunication] = React.useState(profile.communication); const [structure, setStructure] = React.useState(profile.structure)
  return <div className="modal-backdrop"><div className="panel modal-panel"><h2>Edit {profile.display_name}</h2><div className="field-grid"><label>Hours per week<input type="number" min={0} max={10} value={hours} onChange={(e) => setHours(Number(e.target.value))} /></label><label>Role preference<select value={role} onChange={(e) => setRole(e.target.value)}>{['lead','flexible','support'].map((x) => <option key={x}>{x}</option>)}</select></label><label>Communication<select value={communication} onChange={(e) => setCommunication(e.target.value)}>{['async','mixed','synchronous'].map((x) => <option key={x}>{x}</option>)}</select></label><label>Structure<select value={structure} onChange={(e) => setStructure(e.target.value)}>{['structured','flexible','spontaneous'].map((x) => <option key={x}>{x}</option>)}</select></label></div><div className="form-actions"><button className="button primary" disabled={busy} onClick={() => onSave({ ...profile, weekly_hours: hours, role_preference: role, communication, structure })}>Save profile</button><button className="quiet-button" onClick={onCancel}>Cancel</button></div></div></div>
}

function TeamPage({ project, profiles, profileRevision, data, suggestion, busy, onSuggest, onExplain, onSave, onRoadmap, onRefresh }: { project: Project; profiles: Profile[]; profileRevision: number; data: any; suggestion: any; busy: boolean; onSuggest: () => void; onExplain: (id: string) => Promise<string | null>; onSave: (ids: string[]) => void; onRoadmap: () => void; onRefresh: () => void }) {
  const [selected, setSelected] = React.useState<string[]>(project.member_ids)
  const [explanation, setExplanation] = React.useState<{ profileId: string; text: string } | null>(null)
  const [explainingId, setExplainingId] = React.useState<string | null>(null)
  React.useEffect(() => setSelected(project.member_ids), [project.id, project.team_revision])
  const suggestions = suggestion?.steps?.length ? suggestion : data
  const recommended = suggestions?.steps?.[0]?.candidate?.profile_id
  const coverage = suggestions?.current_coverage ?? suggestions?.coverage ?? data?.current_coverage ?? data?.coverage ?? []
  const missingPiece = suggestions?.current_missing_piece ?? suggestions?.missing_piece ?? data?.current_missing_piece ?? data?.missing_piece
  const canAdd = selected.length < project.desired_team_size
  return <section className="workflow"><StepHeader step="03 / TEAM BUILDER" title="Choose your mix." description="Review the current coverage, compare candidate evidence, then save the people you want on this project." /><div className="team-summary"><div className="panel coverage-panel"><div className="panel-heading"><div><div className="eyebrow">CURRENT TEAM COVERAGE</div><h2>{selected.length} of {project.desired_team_size} people</h2></div><button className="quiet-button" onClick={onRefresh}>Refresh</button></div>{project.requirements?.skill_requirements.map((requirement) => { const row = coverage.find((item: any) => item.skill === requirement.skill); return <div className="coverage-row" key={requirement.id}><span>{requirement.skill.replaceAll('_', ' ')}</span><div className="meter"><i style={{ width: `${Math.max(4, Math.min(100, (row?.coverage ?? 0) * 100))}%` }} /></div><small>{row?.coverage >= 1 ? 'Covered' : requirement.critical ? 'Critical' : 'Team need'}</small></div> })}</div><div className="panel missing-panel"><div className="eyebrow">MISSING PIECE</div><h3>{missingPiece?.label ?? missingPiece?.skill ?? 'No current skill gap'}</h3><p>{missingPiece?.coverage != null ? `${Math.round(missingPiece.coverage * 100)}% coverage · ${missingPiece.critical ? 'Release-blocking skill gap' : 'Opportunity to add capacity'}` : 'The selected team currently meets the confirmed skill targets.'}</p><button className="button secondary" disabled={busy} onClick={onSuggest}>Suggest a complementary team</button></div></div>
    <div className="panel candidate-panel"><div className="panel-heading"><div><div className="eyebrow">AVAILABLE PROFILES</div><h2>Choose deliberately.</h2></div><span className="muted">Scores are heuristic evidence, not success probabilities.</span></div><div className="candidate-list">{profiles.map((profile, i) => { const isSelected = selected.includes(profile.id); const step = suggestions?.steps?.find((s: any) => s.candidate?.profile_id === profile.id); const score = step?.considered?.find((c: any) => c.profile_id === profile.id)?.general_score; return <article className={`candidate ${isSelected ? 'candidate-selected' : ''}`} key={profile.id}><span className={`avatar avatar-${i % 4}`}>{profile.display_name[0]}</span><div className="candidate-main"><b>{profile.display_name}{profile.id === recommended && <span className="recommend-label">Suggested next</span>}</b><small>{Object.keys(profile.skills).slice(0, 4).map((x) => x.replaceAll('_', ' ')).join(' · ')} · {profile.weekly_hours ?? 0}h/wk</small></div><span className="candidate-score">{score == null ? '—' : `${Math.round(score * 100)}%`}<small>context fit</small></span><button className="quiet-button" disabled={busy || (!isSelected && !canAdd)} onClick={() => setSelected((current) => isSelected ? current.filter((id) => id !== profile.id) : [...current, profile.id])}>{isSelected ? 'Remove' : 'Add'}</button><button className="quiet-button" disabled={busy || isSelected || explainingId === profile.id} aria-label={explanation?.profileId === profile.id ? 'Hide explanation' : 'Why this fit?'} aria-expanded={explanation?.profileId === profile.id} onClick={async () => { if (explanation?.profileId === profile.id) { setExplanation(null); return } setExplainingId(profile.id); const text = await onExplain(profile.id); setExplainingId(null); if (text) setExplanation({ profileId: profile.id, text }) }}>{explainingId === profile.id ? 'Checking…' : explanation?.profileId === profile.id ? 'Hide' : 'Why?'}</button>{explanation?.profileId === profile.id && <p className="candidate-explanation" role="status">{explanation.text}</p>}</article> })}</div><div className="form-actions"><span className="muted">Selected: {selected.length}/{project.desired_team_size}</span><button className="button primary" disabled={busy || selected.length > project.desired_team_size} onClick={() => onSave(selected)}>Save my team</button>{project.member_ids.length > 0 && <button className="button secondary" onClick={onRoadmap}>Open roadmap →</button>}</div></div>
    {suggestion && <div className="notice">Recommendation refreshed against profile revision {profileRevision}. Save your selection to apply changes.</div>}
  </section>
}

function RoadmapPage({ project, profiles, profileRevision, data, roadmap, busy, onDraft, onSave, onTaskStatus }: { project: Project; profiles: Profile[]; profileRevision: number; data: any; roadmap: Roadmap | null; busy: boolean; onDraft: () => void; onSave: (roadmap: Roadmap, source: string) => void; onTaskStatus: (task: Task, status: Task['status']) => void }) {
  const [draft, setDraft] = React.useState<Roadmap | null>(roadmap)
  const [confirmingReplace, setConfirmingReplace] = React.useState(false)
  React.useEffect(() => setDraft(roadmap), [roadmap?.revision, roadmap?.milestones.length, roadmap?.draft_pending])
  const updateTask = (taskId: string, patch: Partial<Task>) => setDraft((current) => current ? { ...current, milestones: current.milestones.map((milestone) => ({ ...milestone, tasks: milestone.tasks.map((task) => task.id === taskId ? { ...task, ...patch } : task) })) } : current)
  const saveDraft = () => { if (!draft) return; onSave(draft, draft.source ?? 'manual') }
  return <section className="workflow"><StepHeader step="04 / ROADMAP" title="Turn the team into a first plan." description="Generate an editable plan, review owners and hours, and save it. Progress stays attached to this session." /><div className="panel roadmap-panel"><div className="panel-heading"><div><div className="eyebrow">{roadmap?.draft_pending ? roadmap.id ? `REPLACEMENT DRAFT · REVISION ${roadmap.revision} TO REPLACE` : 'EDITABLE DRAFT · NOT SAVED' : roadmap?.id ? `SAVED PLAN · REVISION ${roadmap.revision}` : roadmap ? 'EDITABLE DRAFT · NOT SAVED' : 'NO SAVED PLAN YET'}</div><h2>{project.title}</h2><p className="muted">{data?.coverage ? 'Team coverage is available for planning.' : 'Review team coverage before assigning work.'} · profiles r{profileRevision}</p></div><button className="button secondary" disabled={busy || project.member_ids.length === 0} onClick={onDraft}>Generate editable draft</button></div>{roadmap?.stale && <p className="alert">Team or project inputs changed since this plan was saved. Review and save a refreshed plan.</p>}{!draft && <div className="empty-state"><p>No roadmap is saved. Draft one from the confirmed requirements and selected team.</p></div>}{draft && <><div className="milestone-list">{draft.milestones.map((milestone) => <article className="milestone" key={milestone.id ?? milestone.week}><div className="milestone-heading"><span>WEEK {milestone.week}</span><div><input value={milestone.title} aria-label={`Week ${milestone.week} title`} onChange={(e) => setDraft((current) => current ? { ...current, milestones: current.milestones.map((m) => m.week === milestone.week ? { ...m, title: e.target.value } : m) } : current)} /><textarea rows={2} value={milestone.objective} aria-label={`Week ${milestone.week} objective`} onChange={(e) => setDraft((current) => current ? { ...current, milestones: current.milestones.map((m) => m.week === milestone.week ? { ...m, objective: e.target.value } : m) } : current)} /></div></div>{milestone.tasks.map((task) => <div className="task-row" key={task.id ?? `${milestone.week}-${task.title}`}><div><b>{task.title}</b><small>{task.definition_of_done} · {task.required_skill ?? 'team'} · {task.estimated_hours}h</small></div><span>{profiles.find((p) => p.id === task.owner_id)?.display_name ?? 'Unassigned'}</span>{task.id ? <select aria-label={`${task.title} status`} value={task.status} onChange={(e) => onTaskStatus(task, e.target.value as Task['status'])}><option value="todo">To do</option><option value="doing">In progress</option><option value="done">Done</option></select> : <span className="draft-label">Draft</span>}</div>)}</article>)}</div><div className="form-actions"><span className="muted">Tasks: {draft.milestones.reduce((count, m) => count + m.tasks.length, 0)}</span><button className="button primary" disabled={busy} onClick={() => roadmap?.id ? setConfirmingReplace(true) : saveDraft()}>{roadmap?.draft_pending ? roadmap.id ? 'Save refreshed roadmap' : 'Save roadmap' : roadmap?.id ? 'Replace saved roadmap' : 'Save roadmap'}</button></div></>}</div>{confirmingReplace && draft && <div className="modal-backdrop"><div className="panel modal-panel" role="alertdialog" aria-modal="true" aria-labelledby="replace-roadmap-title"><div className="eyebrow">REPLACE ROADMAP</div><h2 id="replace-roadmap-title">Replace the saved plan?</h2><p className="muted">Replacing this roadmap removes its existing tasks and resets their progress. Review the refreshed plan before continuing.</p><div className="form-actions"><button className="quiet-button" onClick={() => setConfirmingReplace(false)}>Cancel</button><button className="button primary" onClick={() => { setConfirmingReplace(false); saveDraft() }}>Replace plan and reset task progress</button></div></div></div>}</section>
}

function StepHeader({ step, title, description }: { step: string; title: string; description: string }) { return <header className="workflow-header"><div className="eyebrow">{step}</div><h1>{title}</h1><p>{description}</p></header> }

const root = createRoot(document.getElementById('root')!)
if (import.meta.hot) import.meta.hot.dispose(() => root.unmount())
root.render(<React.StrictMode><App /></React.StrictMode>)
