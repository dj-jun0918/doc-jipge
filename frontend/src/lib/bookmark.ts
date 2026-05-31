const BOOKMARK_KEY = "doc-jipge-bookmarks";

/**
 * 저장된 북마크 ID 목록을 반환합니다.
 */
export function getBookmarks(): string[] {
  if (typeof window === "undefined") return [];
  const data = localStorage.getItem(BOOKMARK_KEY);
  if (!data) return [];
  try {
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.error("Failed to parse bookmarks", e);
    return [];
  }
}

/**
 * 특정 ID가 북마크되어 있는지 확인합니다.
 */
export function isBookmarked(id: string | number): boolean {
  const bookmarks = getBookmarks();
  return bookmarks.includes(String(id));
}

/**
 * 북마크에 ID를 추가합니다.
 */
export function addBookmark(id: string | number): void {
  if (typeof window === "undefined") return;
  const bookmarks = getBookmarks();
  const idStr = String(id);
  
  if (!bookmarks.includes(idStr)) {
    bookmarks.push(idStr);
    localStorage.setItem(BOOKMARK_KEY, JSON.stringify(bookmarks));
  }
}

/**
 * 북마크에서 ID를 제거합니다.
 */
export function removeBookmark(id: string | number): void {
  if (typeof window === "undefined") return;
  const bookmarks = getBookmarks();
  const idStr = String(id);
  
  const updated = bookmarks.filter((b) => b !== idStr);
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify(updated));
}

/**
 * 북마크 상태를 토글합니다.
 * @returns 변경된 후의 북마크 상태 (true: 추가됨, false: 삭제됨)
 */
export function toggleBookmark(id: string | number): boolean {
  if (isBookmarked(id)) {
    removeBookmark(id);
    return false;
  } else {
    addBookmark(id);
    return true;
  }
}
