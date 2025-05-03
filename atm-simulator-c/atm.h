#ifndef ATM_H
#define ATM_H

#define MAX_ACCOUNTS 10
#define MAX_HISTORY 20

typedef struct {
    int number;
    char nip[5];
    float balance;
    char history[MAX_HISTORY][50];
    int history_count;
} Account;

extern Account accounts[MAX_ACCOUNTS];
extern int account_count;
extern int current_index;

void load_accounts();
void save_accounts();
void login_menu();
void operations_menu();
void deposit();
void withdraw();
void show_history();

#endif