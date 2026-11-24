import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Учебное однопоточное ядро A1-A3. Java 21, без внешних зависимостей. */
public final class FitnessClub {
  public enum Status { PENDING, ACTIVE, EXPIRED, TERMINATED }
  public record Result(boolean allowed, String reason) {
    static Result no(String reason) { return new Result(false, reason); }
    static Result yes() { return new Result(true, "OK"); }
  }
  public record Period(LocalDate from, LocalDate to) {
    public boolean contains(LocalDate day) {
      return !day.isBefore(from) && day.isBefore(to);
    }
    public boolean overlaps(Period other) {
      return from.isBefore(other.to) && other.from.isBefore(to);
    }
  }
  public record Tariff(int durationDays, int maxFreezeDays,
                       boolean daytime, Set<String> zones) {
    public Tariff {
      if (durationDays <= 0 || maxFreezeDays < 0 || zones == null) {
        throw new IllegalArgumentException("Invalid tariff");
      }
      zones = Set.copyOf(zones);
    }
  }
  public static LocalDate calcEndDate(LocalDate start, int duration,
                                      int freezes) {
    if (duration <= 0 || freezes < 0) {
      throw new IllegalArgumentException("Invalid duration");
    }
    return start.plusDays((long) duration + freezes);
  }
  public abstract static class Subscription {
    private final String card;
    private final Tariff tariff;
    private Status status = Status.PENDING;
    private LocalDate start;
    private LocalDate end;
    private boolean debt;
    private int freezeDaysUsed;
    private final List<Period> freezes = new ArrayList<>();
    protected Subscription(String card, Tariff tariff) {
      if (card == null || card.isBlank() || tariff == null) {
        throw new IllegalArgumentException("Invalid subscription");
      }
      this.card = card;
      this.tariff = tariff;
    }
    public String card() { return card; }
    public Status status() { return status; }
    public LocalDate start() { return start; }
    public LocalDate end() { return end; }
    public int freezeDaysUsed() { return freezeDaysUsed; }
    public List<Period> freezes() { return List.copyOf(freezes); }
    public void setDebt(boolean debt) { this.debt = debt; }
    public void terminate() { status = Status.TERMINATED; }
    private void activate(LocalDate day) {
      start = day;
      end = calcEndDate(day, tariff.durationDays(), freezeDaysUsed);
      status = Status.ACTIVE;
    }
    protected abstract boolean hasVisits();
    protected abstract void consumeVisit();
  }
  public static final class TermSubscription extends Subscription {
    public TermSubscription(String card, Tariff tariff) {
      super(card, tariff);
    }
    protected boolean hasVisits() { return true; }
    protected void consumeVisit() { }
  }
  public static final class VisitSubscription extends Subscription {
    private int visitsLeft;
    public VisitSubscription(String card, Tariff tariff, int visits) {
      super(card, tariff);
      if (visits <= 0) throw new IllegalArgumentException("Invalid visits");
      visitsLeft = visits;
    }
    public int visitsLeft() { return visitsLeft; }
    protected boolean hasVisits() { return visitsLeft > 0; }
    protected void consumeVisit() { visitsLeft--; }
  }
  public interface SubscriptionRepository {
    Subscription findByCard(String card);
    void add(Subscription subscription);
  }
  public static final class InMemoryRepository
      implements SubscriptionRepository {
    private final Map<String, Subscription> cards = new HashMap<>();
    public Subscription findByCard(String card) { return cards.get(card); }
    public void add(Subscription sub) {
      if (cards.putIfAbsent(sub.card(), sub) != null) {
        throw new IllegalArgumentException("Duplicate card");
      }
    }
  }
  public static final class Visit {
    private final String card;
    private final String zone;
    private final LocalDateTime entered;
    private LocalDateTime exited;
    private Visit(String card, String zone, LocalDateTime entered) {
      this.card = card;
      this.zone = zone;
      this.entered = entered;
    }
    public String card() { return card; }
    public String zone() { return zone; }
    public LocalDateTime entered() { return entered; }
    public LocalDateTime exited() { return exited; }
  }
  public static final class ClubService {
    private final SubscriptionRepository repository;
    private final List<Visit> visits = new ArrayList<>();
    private final Map<String, Visit> openVisits = new HashMap<>();
    public ClubService(SubscriptionRepository repository) {
      this.repository = repository;
    }
    public List<Visit> visits() { return List.copyOf(visits); }
    public void register(Subscription sub, LocalDate purchaseActivation) {
      // Сначала проверка уникальности карты, затем активация.
      repository.add(sub);
      if (purchaseActivation != null) sub.activate(purchaseActivation);
    }
    public Result checkAccess(String card, String zone, LocalDateTime when) {
      Subscription sub = repository.findByCard(card);
      if (sub == null) return Result.no("unknown card");
      if (sub.status == Status.TERMINATED) return Result.no("terminated");
      LocalDate day = when.toLocalDate();
      boolean pending = sub.status == Status.PENDING;
      LocalDate start = pending ? day : sub.start;
      LocalDate end = pending
          ? calcEndDate(day, sub.tariff.durationDays(), 0) : sub.end;
      if (sub.status == Status.EXPIRED || !day.isBefore(end)) {
        return Result.no("expired");
      }
      if (day.isBefore(start)) return Result.no("not started");
      for (Period period : sub.freezes) {
        if (period.contains(day)) return Result.no("frozen");
      }
      if (!sub.hasVisits()) return Result.no("no visits left");
      LocalTime time = when.toLocalTime();
      if (time.isBefore(LocalTime.of(7, 0))
          || !time.isBefore(LocalTime.of(23, 0))) {
        return Result.no("closed");
      }
      if (sub.tariff.daytime() && !time.isBefore(LocalTime.of(17, 0))) {
        return Result.no("outside tariff hours");
      }
      if (!sub.tariff.zones().contains(zone)) return Result.no("wrong zone");
      if (sub.debt) return Result.no("debt");
      if (openVisits.containsKey(card)) return Result.no("already entered");
      // Только успешная проверка изменяет состояние.
      if (pending) sub.activate(day);
      Visit visit = new Visit(card, zone, when);
      visits.add(visit);
      openVisits.put(card, visit);
      sub.consumeVisit();
      return Result.yes();
    }
    public boolean exitVisit(String card, LocalDateTime when) {
      Visit visit = openVisits.get(card);
      if (visit == null || when.isBefore(visit.entered)) return false;
      openVisits.remove(card);
      visit.exited = when;
      return true;
    }
    public Result freeze(String card, LocalDate from, int days,
                         LocalDate requested) {
      Subscription sub = repository.findByCard(card);
      if (sub == null) return Result.no("unknown card");
      if (sub.status != Status.ACTIVE) return Result.no("not active");
      if (days <= 0) return Result.no("invalid days");
      if (from.isBefore(requested)) return Result.no("past date");
      if (from.isBefore(sub.start) || !from.isBefore(sub.end)) {
        return Result.no("outside subscription period");
      }
      if ((long) sub.freezeDaysUsed + days > sub.tariff.maxFreezeDays()) {
        return Result.no("freeze limit");
      }
      Period period = new Period(from, from.plusDays(days));
      for (Period old : sub.freezes) {
        if (period.overlaps(old)) return Result.no("overlap");
      }
      LocalDate newEnd = calcEndDate(sub.start, sub.tariff.durationDays(),
                                    sub.freezeDaysUsed + days);
      sub.freezes.add(period);
      sub.freezeDaysUsed += days;
      sub.end = newEnd;
      return Result.yes();
    }
  }
  public static void main(String[] args) {
    ClubService service = new ClubService(new InMemoryRepository());
    Tariff tariff = new Tariff(30, 14, false, Set.of("gym", "pool"));
    Subscription sub = new TermSubscription("CARD-001", tariff);
    service.register(sub, LocalDate.of(2026, 11, 2));
    System.out.println("End exclusive: " + sub.end());
    System.out.println(service.checkAccess("CARD-001", "gym",
        LocalDateTime.of(2026, 11, 3, 9, 30)));
    System.out.println(service.freeze("CARD-001", LocalDate.of(2026, 11, 10),
        10, LocalDate.of(2026, 11, 3)));
    System.out.println("New end exclusive: " + sub.end());
  }
}
