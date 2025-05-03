#include <stdio.h>
#include <string.h>
#include "atm.h"

Account accounts[MAX_ACCOUNTS];
int account_count = 0;
int current_index = -1;

void load_accounts() {
    FILE *file = fopen("accounts.dat", "rb");
    if (file != NULL) {
        fread(&account_count, sizeof(int), 1, file);
        fread(accounts, sizeof(Account), account_count, file);
        fclose(file);
    }
}

void save_accounts() {
    FILE *file = fopen("accounts.dat", "wb");
    if (file != NULL) {
        fwrite(&account_count, sizeof(int), 1, file);
        fwrite(accounts, sizeof(Account), account_count, file);
        fclose(file);
    }
}

void login_menu() {
    char nip[5];
    int acc_num;
    printf("Enter account number: ");
    scanf("%d", &acc_num);
    printf("Enter NIP: ");
    scanf("%s", nip);
    for (int i = 0; i < account_count; i++) {
        if (accounts[i].number == acc_num && strcmp(accounts[i].nip, nip) == 0) {
            current_index = i;
            operations_menu();
            return;
        }
    }
    printf("Invalid credentials.\n");
}

void operations_menu() {
    int choice;
    do {
        printf("\n1. Balance\n2. Deposit\n3. Withdraw\n4. History\n5. Exit\nChoose: ");
        scanf("%d", &choice);
        switch (choice) {
            case 1: printf("Balance: %.2f\n", accounts[current_index].balance); break;
            case 2: deposit(); break;
            case 3: withdraw(); break;
            case 4: show_history(); break;
        }
    } while (choice != 5);
}

void deposit() {
    float amount;
    printf("Enter amount to deposit: ");
    scanf("%f", &amount);
    accounts[current_index].balance += amount;
    sprintf(accounts[current_index].history[accounts[current_index].history_count++], "Deposit: %.2f", amount);
}

void withdraw() {
    float amount;
    printf("Enter amount to withdraw: ");
    scanf("%f", &amount);
    if (amount > accounts[current_index].balance) {
        printf("Insufficient funds.\n");
        return;
    }
    accounts[current_index].balance -= amount;
    sprintf(accounts[current_index].history[accounts[current_index].history_count++], "Withdraw: %.2f", amount);
}

void show_history() {
    for (int i = 0; i < accounts[current_index].history_count; i++) {
        printf("%s\n", accounts[current_index].history[i]);
    }
}