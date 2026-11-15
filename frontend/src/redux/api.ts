import {createApi, fetchBaseQuery} from '@reduxjs/toolkit/query/react';
import type {
  Board,
  BoardInput,
  BoardValidation,
  Mark,
  MarkStatus,
  Platform,
  Posting,
  PostingsQuery,
  PostingsResponse,
  Preset,
  Profile,
  ProfileInput,
  Settings,
} from '../datatypes';

const API_URL: string = import.meta.env.VITE_API_URL ?? '';

export function postingsParams(query: PostingsQuery): Record<string, string> {
  const params: Record<string, string> = {};
  if (query.profile !== undefined) params.profile = String(query.profile);
  if (query.maxAgeDays !== undefined) params.maxAgeDays = String(query.maxAgeDays);
  if (query.workType?.length) params.workType = query.workType.join(',');
  if (query.employmentType?.length) params.employmentType = query.employmentType.join(',');
  if (query.local) params.local = 'true';
  return params;
}

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({baseUrl: `${API_URL}/api`}),
  tagTypes: ['Postings', 'Boards', 'Profiles', 'Settings', 'Marks'],
  endpoints: (build) => ({
    getPostings: build.query<PostingsResponse, PostingsQuery>({
      query: (query) => ({url: 'postings', params: postingsParams(query)}),
      providesTags: ['Postings'],
    }),
    refresh: build.mutation<{started: boolean}, void>({
      query: () => ({url: 'refresh', method: 'POST'}),
    }),
    recordVisit: build.mutation<{new_since: string | null}, void>({
      query: () => ({url: 'visits', method: 'POST'}),
      invalidatesTags: ['Postings'],
    }),

    getPlatforms: build.query<Platform[], void>({query: () => 'platforms'}),
    getBoards: build.query<Board[], void>({query: () => 'boards', providesTags: ['Boards']}),
    validateBoard: build.mutation<BoardValidation, BoardInput>({
      query: (body) => ({url: 'boards/validate', method: 'POST', body}),
    }),
    createBoard: build.mutation<Board, BoardInput>({
      query: (body) => ({url: 'boards', method: 'POST', body}),
      invalidatesTags: ['Boards'],
    }),
    updateBoard: build.mutation<Board, {id: number} & Partial<BoardInput>>({
      query: ({id, ...body}) => ({url: `boards/${id}`, method: 'PATCH', body}),
      invalidatesTags: ['Boards', 'Postings'],
    }),
    deleteBoard: build.mutation<void, number>({
      query: (id) => ({url: `boards/${id}`, method: 'DELETE'}),
      invalidatesTags: ['Boards', 'Postings'],
    }),

    getProfiles: build.query<Profile[], void>({
      query: () => 'profiles',
      providesTags: ['Profiles'],
    }),
    getPresets: build.query<Preset[], void>({query: () => 'profiles/presets'}),
    createProfile: build.mutation<Profile, ProfileInput>({
      query: (body) => ({url: 'profiles', method: 'POST', body}),
      invalidatesTags: ['Profiles'],
    }),
    updateProfile: build.mutation<Profile, {id: number} & Partial<ProfileInput>>({
      query: ({id, ...body}) => ({url: `profiles/${id}`, method: 'PATCH', body}),
      invalidatesTags: ['Profiles', 'Postings'],
    }),
    deleteProfile: build.mutation<void, number>({
      query: (id) => ({url: `profiles/${id}`, method: 'DELETE'}),
      invalidatesTags: ['Profiles'],
    }),

    getSettings: build.query<Settings, void>({
      query: () => 'settings',
      providesTags: ['Settings'],
    }),
    updateSettings: build.mutation<Settings, Partial<Settings>>({
      query: (body) => ({url: 'settings', method: 'PUT', body}),
      invalidatesTags: ['Settings', 'Postings'],
    }),

    getMarks: build.query<Mark[], void>({query: () => 'marks', providesTags: ['Marks']}),
    addMark: build.mutation<Mark, {posting: Posting; status: MarkStatus}>({
      query: ({posting, status}) => ({
        url: 'marks',
        method: 'POST',
        body: {
          org: posting.org,
          title: posting.title,
          location: posting.location,
          url: posting.url,
          status,
        },
      }),
      invalidatesTags: ['Marks', 'Postings'],
    }),
    removeMark: build.mutation<void, string>({
      query: (key) => ({url: 'marks', method: 'DELETE', params: {key}}),
      invalidatesTags: ['Marks', 'Postings'],
    }),
  }),
});

export const {
  useGetPostingsQuery,
  useRefreshMutation,
  useRecordVisitMutation,
  useGetPlatformsQuery,
  useGetBoardsQuery,
  useValidateBoardMutation,
  useCreateBoardMutation,
  useUpdateBoardMutation,
  useDeleteBoardMutation,
  useGetProfilesQuery,
  useGetPresetsQuery,
  useCreateProfileMutation,
  useUpdateProfileMutation,
  useDeleteProfileMutation,
  useGetSettingsQuery,
  useUpdateSettingsMutation,
  useGetMarksQuery,
  useAddMarkMutation,
  useRemoveMarkMutation,
} = api;
