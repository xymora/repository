#include <stdio.h>
#include "atm.h"

int main() {
    load_accounts();
    login_menu();
    save_accounts();
    return 0;
}