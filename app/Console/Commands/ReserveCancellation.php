<?php

namespace App\Console\Commands;

use App\Enums\ReservationStatus;
use App\Models\Reservation;
use Carbon\Carbon;
use Illuminate\Console\Command;

class ReserveCancellation extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'app:reserve-cancellation';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'cancelling failed reservation';

    /**
     * Execute the console command.
     */
    public function handle(): void
    {
        $reservations = Reservation::where("status", "=", ReservationStatus::Pending->value)
            ->whereDate('created_at', '=>', Carbon::now()->subMinutes(15)->toDateTimeString());
        foreach ($reservations as $item){
            if (count($item->buy())){
                $item->cancellation = false;
                $item->save();
            }else{
                $item->status = ReservationStatus::Success;
                $item->save();
            }
        }
    }
}
