#include <iostream>
#include <fstream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc != 3) {
        return 1;
    }

    std::string magnitude = argv[1];
    std::string arrival_time = argv[2];

    std::ofstream outFile("json/earthquake.json");

    if (!outFile) {
        std::cerr << "Failed to open file for writing." << std::endl;
        return 1;
    }

    outFile << "{\n";
    outFile << "  \"地震震度\": \"" << magnitude << "\",\n";
    outFile << "  \"抵達秒數\": \"" << arrival_time << "\",\n";
    outFile << "  \"flag\": \"" << 1 << "\"\n";
    outFile << "}\n";

    outFile.close();

    return 0;
}