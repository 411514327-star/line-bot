from datetime import date
import platform


def main():
    github_user = "411514327-star"
    device_name = platform.node()
    print(f"你好！我是 GitHub 使用者 @{github_user}。")
    print(f"今天是：{date.today()}")
    print(f"執行裝置：{device_name} ({platform.system()})")


if __name__ == "__main__":
    main()
