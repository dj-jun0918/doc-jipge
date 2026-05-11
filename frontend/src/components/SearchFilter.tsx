interface SearchFilterProps {
  keyword: string;
  source: string;
  region: string;
  onKeywordChange: (value: string) => void;
  onSourceChange: (value: string) => void;
  onRegionChange: (value: string) => void;
  showBookmarks: boolean;
  onShowBookmarksChange: (value: boolean) => void;
  onSearch: () => void;
  onReset: () => void;
}

export default function SearchFilter({
  keyword,
  source,
  region,
  onKeywordChange,
  onSourceChange,
  onRegionChange,
  showBookmarks,
  onShowBookmarksChange,
  onSearch,
  onReset,
}: SearchFilterProps) {
  return (
    <div className="mb-6 rounded-2xl border bg-white p-5 shadow-sm">
      <div className="grid gap-4 md:grid-cols-4">
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700">
            키워드
          </label>
          <input
            type="text"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
            placeholder="공고명 검색"
            className="w-full rounded-lg border px-4 py-3"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700">
            출처
          </label>
          <select
            value={source}
            onChange={(e) => onSourceChange(e.target.value)}
            className="w-full rounded-lg border px-4 py-3"
          >
            <option value="">전체</option>
            <option value="bizinfo">기업마당</option>
            <option value="kstartup">K-Startup</option>
            <option value="mss">중기부</option>
          </select>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700">
            지역
          </label>
          <select
            value={region}
            onChange={(e) => onRegionChange(e.target.value)}
            className="w-full rounded-lg border px-4 py-3"
          >
            <option value="">전체</option>
            <option value="서울">서울</option>
            <option value="경기">경기</option>
            <option value="인천">인천</option>
            <option value="강원">강원</option>
            <option value="부산">부산</option>
            <option value="대구">대구</option>
            <option value="대전">대전</option>
            <option value="광주">광주</option>
            <option value="울산">울산</option>
            <option value="세종">세종</option>
            <option value="충북">충북</option>
            <option value="충남">충남</option>
            <option value="전북">전북</option>
            <option value="전남">전남</option>
            <option value="경북">경북</option>
            <option value="경남">경남</option>
            <option value="제주">제주</option>
            <option value="전국">전국</option>
          </select>
        </div>

        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={onSearch}
            className="rounded-lg bg-blue-600 px-5 py-3 text-white hover:bg-blue-700"
          >
            검색
          </button>
          <button
            type="button"
            onClick={onReset}
            className="rounded-lg border px-5 py-3 text-gray-700 hover:bg-gray-50"
          >
            초기화
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 border-t pt-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showBookmarks}
            onChange={(e) => onShowBookmarksChange(e.target.checked)}
            className="h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm font-medium text-gray-700 flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="#EAB308" stroke="#EAB308" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
            북마크만 보기
          </span>
        </label>
      </div>
    </div>
  );
}