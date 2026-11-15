import {fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {AddApplicationForm} from '../components/AddApplicationForm';
import {ApplicationDetail} from '../components/ApplicationDetail';
import {ApplicationsList, StatusBadge} from '../components/ApplicationsList';
import {FilteredOutNotice, StatusFilter} from '../components/ApplicationsTab';
import {applicationsParams} from '../redux/api';
import {application} from './factories';

afterEach(() => vi.restoreAllMocks());

describe('ApplicationsList', () => {
  it('shows an empty message', () => {
    render(<ApplicationsList applications={[]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText('No applications yet.')).toBeTruthy();
  });

  it('renders a card with a link, status and dates', () => {
    const a = application({status: 'applied', applied_at: '2026-03-02T12:00:00Z'});
    render(<ApplicationsList applications={[a]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByRole('link', {name: a.title}).getAttribute('href')).toBe(a.url);
    const card = within(screen.getByRole('listitem'));
    expect(card.getByText('Applied')).toBeTruthy();
    expect(card.getByText(/Elsewhere Inc · Remote/)).toBeTruthy();
    expect(card.getByText(/^Applied .*2026 · referral$/)).toBeTruthy();
  });

  it('shows the title as text when there is no link', () => {
    const a = application({url: ''});
    render(<ApplicationsList applications={[a]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(a.title)).toBeTruthy();
  });

  it('opens and closes the details of one application', () => {
    const a = application();
    const onSelect = vi.fn();
    const {rerender} = render(
      <ApplicationsList applications={[a]} selectedId={null} onSelect={onSelect} detail={<p>detail</p>} />,
    );
    expect(screen.queryByText('detail')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: `Details for ${a.title}`}));
    expect(onSelect).toHaveBeenCalledWith(a.id);

    rerender(
      <ApplicationsList applications={[a]} selectedId={a.id} onSelect={onSelect} detail={<p>detail</p>} />,
    );
    expect(screen.getByText('detail')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: `Close for ${a.title}`}));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it('mutes closed statuses', () => {
    render(<StatusBadge status="rejected" />);
    expect(screen.getByText('Rejected').className).toContain('badge-muted');
  });
});

describe('ApplicationDetail', () => {
  const withHistory = application({
    status: 'screening',
    events: [
      {id: 1, from_status: null, to_status: 'saved', note: '', at: '2026-03-01T12:00:00Z'},
      {id: 2, from_status: 'saved', to_status: 'applied', note: 'online form', at: '2026-03-02T12:00:00Z'},
      {id: 3, from_status: 'applied', to_status: 'screening', note: '', at: '2026-03-05T12:00:00Z'},
    ],
  });

  function renderDetail(handlers: Partial<Parameters<typeof ApplicationDetail>[0]> = {}) {
    const props = {
      application: withHistory,
      onChangeStatus: vi.fn().mockResolvedValue(null),
      onSaveNotes: vi.fn().mockResolvedValue(null),
      onDelete: vi.fn(),
      ...handlers,
    };
    render(<ApplicationDetail {...props} />);
    return props;
  }

  it('lists the history newest first, with notes', () => {
    renderDetail();
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items.map((li) => li.textContent?.replace(/^.*2026 /, ''))).toEqual([
      'Applied → Screening',
      'Saved → Appliedonline form',
      'Added as Saved',
    ]);
  });

  it('changes the status with a note, offering only other statuses', async () => {
    const {onChangeStatus} = renderDetail();
    const select = screen.getByLabelText('New status');
    const options = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(options).not.toContain('Screening');
    expect(options).toHaveLength(8);

    fireEvent.change(select, {target: {value: 'interviewing'}});
    fireEvent.change(screen.getByLabelText('Note (optional)'), {target: {value: ' phone call '}});
    fireEvent.click(screen.getByRole('button', {name: 'Change status'}));
    await waitFor(() => expect(onChangeStatus).toHaveBeenCalledWith('interviewing', 'phone call'));
    await waitFor(() =>
      expect((screen.getByLabelText('Note (optional)') as HTMLInputElement).value).toBe(''),
    );
  });

  it('shows the error when a status change fails', async () => {
    renderDetail({onChangeStatus: vi.fn().mockResolvedValue('the application is already offer')});
    fireEvent.click(screen.getByRole('button', {name: 'Change status'}));
    expect(await screen.findByText('the application is already offer')).toBeTruthy();
  });

  it('saves notes only after they change', async () => {
    const {onSaveNotes} = renderDetail();
    const save = screen.getByRole('button', {name: 'Save notes'});
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Notes'), {target: {value: 'call back Monday'}});
    fireEvent.click(save);
    await waitFor(() => expect(onSaveNotes).toHaveBeenCalledWith('call back Monday'));
    expect(await screen.findByText('Saved', {selector: '.ok'})).toBeTruthy();
  });

  it('trims notes before saving, like the server does', async () => {
    const {onSaveNotes} = renderDetail();
    fireEvent.change(screen.getByLabelText('Notes'), {target: {value: '  follow up  '}});
    fireEvent.click(screen.getByRole('button', {name: 'Save notes'}));
    await waitFor(() => expect(onSaveNotes).toHaveBeenCalledWith('follow up'));
    await waitFor(() => expect((screen.getByLabelText('Notes') as HTMLTextAreaElement).value).toBe('follow up'));
  });

  it('does not offer to save whitespace-only edits', () => {
    renderDetail();
    fireEvent.change(screen.getByLabelText('Notes'), {target: {value: '   '}});
    expect((screen.getByRole('button', {name: 'Save notes'}) as HTMLButtonElement).disabled).toBe(true);
  });

  it('deletes only after confirming', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    const {onDelete} = renderDetail();
    const button = screen.getByRole('button', {name: 'Delete application'});
    fireEvent.click(button);
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(button);
    expect(onDelete).toHaveBeenCalledOnce();
    expect(confirm).toHaveBeenCalledTimes(2);
  });
});

describe('AddApplicationForm', () => {
  it('submits trimmed fields, defaulting to Applied', async () => {
    const onSubmit = vi.fn().mockResolvedValue(null);
    render(<AddApplicationForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Job title'), {target: {value: ' Data Analyst '}});
    fireEvent.change(screen.getByLabelText('Organization'), {target: {value: 'Elsewhere Inc'}});
    fireEvent.change(screen.getByLabelText('Job link'), {target: {value: 'https://example.com/1'}});
    fireEvent.change(screen.getByLabelText('Where you found it'), {target: {value: 'referral'}});
    fireEvent.click(screen.getByRole('button', {name: 'Add application'}));
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        title: 'Data Analyst',
        org: 'Elsewhere Inc',
        location: '',
        url: 'https://example.com/1',
        source: 'referral',
        status: 'applied',
        notes: '',
        note: '',
      }),
    );
  });

  it('shows the server error', async () => {
    const onSubmit = vi.fn().mockResolvedValue('url must start with http:// or https://');
    render(<AddApplicationForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Job title'), {target: {value: 'X'}});
    fireEvent.change(screen.getByLabelText('Organization'), {target: {value: 'Y'}});
    fireEvent.click(screen.getByRole('button', {name: 'Add application'}));
    expect(await screen.findByText('url must start with http:// or https://')).toBeTruthy();
  });

  it('cancels', () => {
    const onCancel = vi.fn();
    render(<AddApplicationForm onSubmit={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', {name: 'Cancel'}));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});

describe('applicationsParams', () => {
  it('sends no status when none is ticked, so every status is listed', () => {
    expect(applicationsParams([])).toEqual({});
  });
  it('joins the ticked statuses', () => {
    expect(applicationsParams(['applied', 'interviewing'])).toEqual({status: 'applied,interviewing'});
  });
});

describe('StatusFilter', () => {
  it('shows every status when none is ticked', () => {
    render(<StatusFilter selected={[]} onChange={vi.fn()} />);
    expect(screen.getAllByRole('checkbox')).toHaveLength(9);
    expect(screen.getAllByRole('checkbox').every((c) => !(c as HTMLInputElement).checked)).toBe(true);
    expect(screen.getByText(/Showing every status/)).toBeTruthy();
    expect(screen.queryByRole('button', {name: 'Show all'})).toBeNull();
  });

  it('ticks and unticks a status', () => {
    const onChange = vi.fn();
    const {rerender} = render(<StatusFilter selected={[]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Offer'));
    expect(onChange).toHaveBeenLastCalledWith(['offer']);

    rerender(<StatusFilter selected={['offer', 'applied']} onChange={onChange} />);
    expect((screen.getByLabelText('Offer') as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(/Showing the ticked statuses/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Offer'));
    expect(onChange).toHaveBeenLastCalledWith(['applied']);
  });

  it('clears the filter with Show all', () => {
    const onChange = vi.fn();
    render(<StatusFilter selected={['offer']} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', {name: 'Show all'}));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });
});

describe('FilteredOutNotice', () => {
  it('explains why the application left the list and offers to show all', () => {
    const onShowAll = vi.fn();
    render(<FilteredOutNotice title="Data Analyst" status="rejected" onShowAll={onShowAll} />);
    expect(screen.getByText(/“Data Analyst” \(Rejected\) is hidden by the status filter/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Show all statuses'}));
    expect(onShowAll).toHaveBeenCalledOnce();
  });
});
