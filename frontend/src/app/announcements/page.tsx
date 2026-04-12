// 가짜 데이터 (PR#2에서 백엔드 API 연동 예정)
const mockAnnouncements = [
  {
    id: "1",
    title: "2026 강원 청년창업 지원사업",
    organization: "강원특별자치도",
    period: "2026-04-01 ~ 2026-04-30",
    region: "강원",
  },
  {
    id: "2",
    title: "2026년 중소기업 수출 바우처 지원",
    organization: "중소벤처기업부",
    period: "2026-04-10 ~ 2026-05-10",
    region: "전국",
  },
  {
    id: "3",
    title: "2026 제조기업 디지털 전환 지원",
    organization: "기업마당",
    period: "2026-04-05 ~ 2026-04-20",
    region: "전국",
  },
];

export default function AnnouncementsPage() {
  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">공고 목록</h1>
      <div className="space-y-4">
        {mockAnnouncements.map((ann) => (
          <div key={ann.id} className="border rounded-lg p-4 hover:shadow-md">
            <h2 className="text-xl font-semibold">{ann.title}</h2>
            <p className="text-gray-600 mt-1">{ann.organization}</p>
            <div className="flex gap-4 mt-2 text-sm text-gray-500">
              <span>접수: {ann.period}</span>
              <span>지역: {ann.region}</span>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}