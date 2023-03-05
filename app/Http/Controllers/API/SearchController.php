<?php

namespace App\Http\Controllers\API;

use App\Classes\Encoding;
use App\Classes\ProjectResource;
use App\Enums\SettingsSystem;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\SearchWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Carbon\Carbon;
use Symfony\Component\HttpFoundation\Response;

class SearchController extends Controller
{
    /**
     * @OA\Get(
     *      path="/searches",
     *      operationId="Lists",
     *      tags={"source", "destination", "datetime"},
     *      summary="Get list of travells ",
     *      description="Returns json list of weekly schedule",
     *      @OA\Response(
     *          response=200,
     *          description="Successful operation",
     *          @OA\JsonResponse(ref="#/components/schemas/ProjectResource")
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found"
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Http Bad Request"
     *      )
     *     )
     */
    public function index(SearchWeeklyScheduleRequest $request)
    {
        if ($request->validated()){
            $source = $request->input("source");
            $destination = $request->input("destination");
            $max_date = Carbon::now()->addWeeks(SettingsSystem::Max_Week);
            $user_date = Carbon::parse($request->input("datetime"));
            if (!$user_date->gt($max_date)) {

                $weekly_schedule_city = WeeklySchedule::with("chairs")
                    ->where("source_city_id", $source)
                    ->where("destination_city_id", $destination)
                    ->whereDate("date", "=",$user_date)
                    ->get(["weekly_schedule.*", "chairs.id", "chairs.chairs"]);

                $weekly_schedule_terminal = WeeklySchedule::with("chairs")
                    ->where("source_terminal_id", $source)
                    ->where("destination_terminal_id", $destination)
                    ->whereDate("date", "=",$user_date)
                    ->get(["weekly_schedule.*", "chairs.id", "chairs.chairs"]);

                $data = array_unique($weekly_schedule_city->merge($weekly_schedule_terminal));
                if(count($data)>0){
                    $search_data = null;
                    foreach ($data as $item){
                        $search_data[] = ["search_code" => Encoding::base64url_encode($item["weekly_schedule.id"]."|".$item["weekly_schedule.id"]), "item" => $item];
                    }
                    return (new ProjectResource($search_data))
                        ->response()
                        ->setStatusCode(Response::HTTP_OK)
                        ->header('Content-Type', 'application/json');
                }else{
                    return response()
                        ->json(['status' => Status::UnSuccess , "code" => StatusCode::UnSuccess, "result" => "couldn't find bus with your order."])
                        ->setStatusCode(Response::HTTP_NOT_FOUND)
                        ->header('Content-Type', 'application/json');
                }
            } else {
                return response()
                    ->json(['status' => Status::UnSuccess , "code" => StatusCode::UnSuccess, "result" => " your date must be lower than ". $max_date])
                    ->setStatusCode(Response::HTTP_BAD_REQUEST)
                    ->header('Content-Type', 'application/json');
            }
        }else{
            return response()
                ->json(['status' => Status::Failed , "code" => StatusCode::HTTP_BAD_REQUEST])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }
}
