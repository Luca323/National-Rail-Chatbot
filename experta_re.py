import collections
import collections.abc
for type_name in ['Mapping','MutableMapping','Iterable','MutableSet']:
    if not hasattr(collections, type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))

from experta import *


# -----------------------------
# FACT DEFINITION
# -----------------------------
class Car(Fact):
    """Facts describing observed car symptoms"""
    pass


# -----------------------------
# EXPERT SYSTEM WITH PRIORITY
# -----------------------------
class CarDoctor(KnowledgeEngine):

    # =============================
    # SAFETY CRITICAL (Highest)
    # =============================
    @Rule(Car(brake_fluid="low"), salience=100)
    def brake_failure(self):
        print("CRITICAL: Brake failure risk — stop vehicle immediately at a safe place!")

    # =============================
    # ENGINE DAMAGE RISK
    # =============================
    @Rule(Car(overheating=True), salience=50)
    def engine_overheat(self):
        print("WARNING: Engine overheating — stop at a safe place and cool engine.")

    # =============================
    # MOBILITY FAILURES
    # =============================
    @Rule(Car(engine_starts=False, battery_voltage="low"), salience=20)
    def dead_battery(self):
        print("Diagnosis: Battery likely dead.")

    @Rule(Car(engine_starts=False, clicking_sound=True), salience=15)
    def starter_fault(self):
        print("Diagnosis: Starter motor may be faulty.")

    # =============================
    # PERFORMANCE ISSUES
    # =============================
    @Rule(Car(headlights_dim=True, engine_starts=True), salience=10)
    def alternator_problem(self):
        print("Diagnosis: Possible alternator charging problem.")

    # =============================
    # MAINTENANCE ISSUES
    # =============================
    @Rule(Car(brake_noise="squealing"), salience=-10)
    def worn_brake_pads(self):
        print("Maintenance: Brake pads worn — replace soon.")

    # =============================
    # FALLBACK
    # =============================
    @Rule(salience=-100)
    def unknown_problem(self):
        print("Cannot diagnose your car's problem. Further inspection is reuqired.")


# -----------------------------
# USER INPUT
# -----------------------------
def ask_boolean(question):
    return input(question + " (yes/no): ").strip().lower() == "yes"


def ask_choice(question, options):
    value = input(f"{question} {options}: ").strip().lower()
    return value


# -----------------------------
# MAIN PROGRAM
# -----------------------------
if __name__ == "__main__":

    print("\n=== CAR FAULT DIAGNOSTIC SYSTEM (PRIORITY MODE) ===\n")


    battery_voltage = ask_choice("Battery voltage", ["low", "normal"])
    clicking_sound = ask_boolean("Clicking sound when turning key?")
    engine_starts = ask_boolean("Does the engine start?")
    headlights_dim = ask_boolean("Headlights dim while driving?")
    overheating = ask_boolean("Engine overheating?")
    brake_fluid = ask_choice("Brake fluid level", ["low", "normal"])
    brake_noise = ask_choice("Brake noise", ["none", "squealing", "grinding"])

    engine = CarDoctor()
    engine.reset()

    engine.declare(Car(
        battery_voltage=battery_voltage,
        clicking_sound=clicking_sound,
        engine_starts=engine_starts,
        headlights_dim=headlights_dim,
        overheating=overheating,
        brake_fluid=brake_fluid,
        brake_noise=brake_noise
    ))

    print("\n--- PRIORITISED DIAGNOSIS ---")
    engine.run()
