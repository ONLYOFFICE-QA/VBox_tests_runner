from frameworks import TestScheduler

if __name__ == "__main__":
    # checker = PackageURLChecker()
    # checker.run("9.0.4.8")

    # Создание экземпляра планировщика
    scheduler = TestScheduler()

    # # Запуск по расписанию (каждые 30 минут с 2:00 до 15:00)
    # scheduler.start_scheduled_tests(
    #     start_hour=14,
    #     end_hour=15,
    #     interval_minutes=30
    # )

    # Просмотр статуса
    status = scheduler.check_and_run_tests()
    print(status)
