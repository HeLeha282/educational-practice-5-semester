import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Set;

public final class FitnessClubTest {
  static int checks;
  static void check(boolean condition) {
    checks++;
    if (!condition) throw new AssertionError("Check " + checks);
  }
  public static void main(String[] args) {
    var repo = new FitnessClub.InMemoryRepository();
    var svc = new FitnessClub.ClubService(repo);
    var tariff = new FitnessClub.Tariff(30, 14, false, Set.of("gym"));
    var sub = new FitnessClub.TermSubscription("A", tariff);
    svc.register(sub, LocalDate.of(2026,11,1));
    check(sub.end().equals(LocalDate.of(2026,12,1)));
    check(svc.checkAccess("A","gym",LocalDateTime.of(2026,11,30,10,0)).allowed());
    check(!svc.checkAccess("A","gym",LocalDateTime.of(2026,11,30,11,0)).allowed());
    svc.exitVisit("A",LocalDateTime.of(2026,11,30,12,0));
    check(!svc.checkAccess("A","gym",LocalDateTime.of(2026,12,1,10,0)).allowed());
    check(sub.status() == FitnessClub.Status.ACTIVE);
    check(!svc.freeze("A",sub.end(),2,LocalDate.of(2026,11,2)).allowed());
    check(sub.freezeDaysUsed() == 0);
    check(svc.freeze("A",LocalDate.of(2026,11,5),2,LocalDate.of(2026,11,2)).allowed());
    check(!svc.freeze("A",LocalDate.of(2026,11,6),2,LocalDate.of(2026,11,2)).allowed());
    check(svc.freeze("A",LocalDate.of(2026,11,7),2,LocalDate.of(2026,11,2)).allowed());
    check(sub.end().equals(LocalDate.of(2026,12,5)));
    check(!svc.freeze("A",LocalDate.of(2026,11,10),15,LocalDate.of(2026,11,2)).allowed());
    var visits = new FitnessClub.VisitSubscription("B",
        new FitnessClub.Tariff(30,14,true,Set.of("gym")), 1);
    svc.register(visits,null);
    check(!svc.checkAccess("B","gym",LocalDateTime.of(2026,11,2,6,0)).allowed());
    check(!svc.checkAccess("B","gym",LocalDateTime.of(2026,11,2,17,0)).allowed());
    check(!svc.checkAccess("B","pool",LocalDateTime.of(2026,11,2,12,0)).allowed());
    visits.setDebt(true);
    check(!svc.checkAccess("B","gym",LocalDateTime.of(2026,11,2,12,0)).allowed());
    check(visits.start() == null && visits.status() == FitnessClub.Status.PENDING);
    check(visits.visitsLeft() == 1 && svc.visits().size() == 1);
    visits.setDebt(false);
    check(svc.checkAccess("B","gym",LocalDateTime.of(2026,11,2,12,0)).allowed());
    check(visits.visitsLeft() == 0);
    svc.exitVisit("B",LocalDateTime.of(2026,11,2,13,0));
    check(!svc.checkAccess("B","gym",LocalDateTime.of(2026,11,2,14,0)).allowed());
    check(!svc.checkAccess("UNKNOWN","gym",LocalDateTime.of(2026,11,2,12,0)).allowed());
    check(!svc.checkAccess("A","gym",LocalDateTime.of(2026,11,5,12,0)).allowed());
    check(svc.checkAccess("A","gym",LocalDateTime.of(2026,11,9,12,0)).allowed());
    System.out.println("OK: " + checks + " checks");
  }
}
